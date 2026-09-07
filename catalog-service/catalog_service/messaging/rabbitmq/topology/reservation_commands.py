from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange, AbstractQueue, AbstractChannel



RESERVATION_EXCHANGE = "stock.reservation.commands"
RESERVATION_REQUEST_QUEUE = "stock.reservation.reservation_requested"
RESERVATION_REQUEST_ROUTING_KEY = "stock.reservation.requested"

RESERVATION_DLX = "stock.reservation.dlx"
RESERVATION_DLQ = "stock.reservation.reservation_requested.dlq"
RESERVATION_DLQ_ROUTING_KEY = "stock.reservation.requested.dead"

RESERVATION_EXCHANGE_RETRY = "stock.reservation.commands.retry"
RESERVATION_REQUEST_RETRY_QUEUE = "stock.reservation.reservation_requested.retry"
RESERVATION_REQUEST_RETRY_ROUTING_KEY = "stock.reservation.requested.retry"

async def declare_reservation_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_EXCHANGE, ExchangeType.DIRECT, durable=True)


async def declare_reservation_requested_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_REQUEST_QUEUE, 
        durable=True,
        arguments={
            "x-dead-letter-exchange": RESERVATION_DLX,
            "x-dead-letter-routing-key": RESERVATION_DLQ_ROUTING_KEY,
        }
    )

async def bind_reservation_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_REQUEST_ROUTING_KEY)


async def declare_reservation_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_DLX, ExchangeType.DIRECT, durable=True)


async def declare_reservation_requested_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(RESERVATION_DLQ, durable=True)

async def bind_reservation_dlq(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_DLQ_ROUTING_KEY)



async def declare_reservation_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_EXCHANGE_RETRY, ExchangeType.DIRECT, durable=True)


async def declare_reservation_retry_requested_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_REQUEST_RETRY_QUEUE, 
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": RESERVATION_EXCHANGE,
            "x-dead-letter-routing-key": RESERVATION_REQUEST_ROUTING_KEY,

        }
    )

async def bind_reservation_retry_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=RESERVATION_REQUEST_RETRY_ROUTING_KEY)