from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


PAYMENT_EVENTS_EXCHANGE = "payments.events"
PAYMENT_RESULTS_QUEUE = "orders.payment_results"
PAYMENT_SUCCEEDED_ROUTING_KEY = "payment.succeeded"
PAYMENT_FAILED_ROUTING_KEY = "payment.failed"


async def declare_payment_events_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        PAYMENT_EVENTS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_payment_results_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_RESULTS_QUEUE, durable=True)


async def bind_payment_results_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_SUCCEEDED_ROUTING_KEY)
    await queue.bind(exchange, routing_key=PAYMENT_FAILED_ROUTING_KEY)
