from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue

RESERVATION_EVENT_EXCHANGE = "stock.reservation.events"
RESERVATION_RESULT_QUEUE = "orders.reservation.reservation_result"
RESERVATION_RESULT_SUCCEEDED_ROUTING_KEY = "stock.reserved"
RESERVATION_RESULT_FAILED_ROUTING_KEY = "stock.reservation.failed"

RESERVATION_DLX = "stock.reservation.dlx"
RESERVATION_RESULT_DLQ = "orders.reservation.reservation_result.dlq"
RESERVATION_RESULT_DLQ_ROUTING_KEY = "orders.reservation_result.dead"

RESERVATION_RESULTS_RETRY_EXCHANGE = "orders.reservation_results.retry"
RESERVATION_RESULTS_RETRY_QUEUE = "orders.reservation_results.retry"
RESERVATION_RESULTS_RETRY_ROUTING_KEY = "stock.reservation.result.retry"
RESERVATION_RESULTS_REDELIVERY_ROUTING_KEY = "stock.reservation.result.redelivery"

async def declare_reservation_result_exchange(
    channel: AbstractChannel,
) -> AbstractExchange:
    return await channel.declare_exchange(
        RESERVATION_EVENT_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_reservation_result_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_RESULT_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": RESERVATION_DLX,
            "x-dead-letter-routing-key": RESERVATION_RESULT_DLQ_ROUTING_KEY,
        },
    )


async def bind_reservation_result_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_RESULT_SUCCEEDED_ROUTING_KEY)
    await queue.bind(exchange, routing_key=RESERVATION_RESULT_FAILED_ROUTING_KEY)
    await queue.bind(exchange, routing_key=RESERVATION_RESULTS_REDELIVERY_ROUTING_KEY)

async def declare_reservation_result_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_DLX, ExchangeType.DIRECT, durable=True)

async def declare_reservation_result_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(RESERVATION_RESULT_DLQ, durable=True)


async def bind_reservation_result_dlq(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_RESULT_DLQ_ROUTING_KEY)


async def declare_reservation_results_retry_exchange(
    channel: AbstractChannel,
) -> AbstractExchange:
    return await channel.declare_exchange(
        RESERVATION_RESULTS_RETRY_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_reservation_results_retry_queue(
    channel: AbstractChannel,
) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_RESULTS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": RESERVATION_EVENT_EXCHANGE,
            "x-dead-letter-routing-key": RESERVATION_RESULTS_REDELIVERY_ROUTING_KEY,
        },
    )

async def bind_reservation_results_retry_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_RESULTS_RETRY_ROUTING_KEY)

