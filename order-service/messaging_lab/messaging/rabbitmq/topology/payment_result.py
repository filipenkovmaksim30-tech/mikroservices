from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


PAYMENT_EVENTS_EXCHANGE = "payments.events"
PAYMENT_RESULTS_QUEUE = "orders.payment_results"
PAYMENT_SUCCEEDED_ROUTING_KEY = "payment.succeeded"
PAYMENT_FAILED_ROUTING_KEY = "payment.failed"


PAYMENT_DLX = "payments.dlx"
PAYMENT_RESULTS_DLQ = "orders.payment_results.dlq"
PAYMENT_RESULTS_DLQ_ROUTING_KEY = "payment.result.dead"

PAYMENT_RESULTS_RETRY_EXCHANGE = "orders.payment_results.retry"
PAYMENT_RESULTS_RETRY_QUEUE = "orders.payment_results.retry"
PAYMENT_RESULTS_RETRY_ROUTING_KEY = "payment.result.retry"
PAYMENT_RESULTS_REDELIVERY_ROUTING_KEY = "payment.result.redelivery"



async def declare_payment_events_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        PAYMENT_EVENTS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_payment_results_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        PAYMENT_RESULTS_QUEUE, 
        durable=True,
        arguments={
            "x-dead-letter-exchange": PAYMENT_DLX,
            "x-dead-letter-routing-key": PAYMENT_RESULTS_DLQ_ROUTING_KEY,
        },
    )


async def bind_payment_results_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_SUCCEEDED_ROUTING_KEY)
    await queue.bind(exchange, routing_key=PAYMENT_FAILED_ROUTING_KEY)
    await queue.bind(exchange, routing_key=PAYMENT_RESULTS_REDELIVERY_ROUTING_KEY)


async def declare_payment_results_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_DLX, ExchangeType.DIRECT, durable=True)

async def declare_payment_results_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_RESULTS_DLQ, durable=True)

async def bind_payment_results_dlq(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_RESULTS_DLQ_ROUTING_KEY)
    


async def declare_payment_results_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_RESULTS_RETRY_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def declare_payment_results_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        PAYMENT_RESULTS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": PAYMENT_EVENTS_EXCHANGE,
            "x-dead-letter-routing-key": PAYMENT_RESULTS_REDELIVERY_ROUTING_KEY,
        },
    )

async def bind_payment_results_retry_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_RESULTS_RETRY_ROUTING_KEY)