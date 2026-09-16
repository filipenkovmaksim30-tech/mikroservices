
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue

RESERVATION_EXCHANGE = "stock.reservation.commands"
RESERVATION_FINALIZATION_QUEUE = "catalog.stock_reservation_finalization"
RESERVATION_FINALIZATION_CONFIRM_ROUTING_KEY = "stock.reservation.confirm.requested"
RESERVATION_FINALIZATION_RELEASE_ROUTING_KEY = "stock.reservation.release.requested"

RESERVATION_DLX = "stock.reservation.dlx"
RESERVATION_FINALIZATION_DLQ = "catalog.reservation.reservation_finalization.dlq"
RESERVATION_FINALIZATION_DLQ_ROUTING_KEY = "catalog.reservation_finalization.dead"

RESERVATION_FINALIZATION_RETRY_EXCHANGE = "stock.reservation.commands.retry"
RESERVATION_FINALIZATION_RETRY_QUEUE = "catalog.reservation_finalization.retry"
RESERVATION_FINALIZATION_RETRY_ROUTING_KEY = "catalog.reservation.finalization.retry"
RESERVATION_FINALIZATION_REDELIVERY_ROUTING_KEY = "catalog.reservation.finalization.redelivery"

async def declare_reservation_finalization_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_EXCHANGE, durable=True)

async def declare_reservation_finalization_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_FINALIZATION_QUEUE, 
        durable=True,
        arguments={
            "x-dead-letter-exchange": RESERVATION_DLX,
            "x-dead-letter-routing-key": RESERVATION_FINALIZATION_DLQ_ROUTING_KEY,
        }
    )

async def bind_reservation_finalization_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, RESERVATION_FINALIZATION_CONFIRM_ROUTING_KEY)
    await queue.bind(exchange, RESERVATION_FINALIZATION_RELEASE_ROUTING_KEY)
    await queue.bind(exchange, RESERVATION_FINALIZATION_REDELIVERY_ROUTING_KEY)


async def declare_reservation_finalization_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_DLX, durable=True)

async def declare_reservation_finalization_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(RESERVATION_FINALIZATION_DLQ, durable=True)

async def bind_reservation_finalization_dlq(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, RESERVATION_FINALIZATION_DLQ_ROUTING_KEY)



async def declare_reservation_finalization_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_FINALIZATION_RETRY_EXCHANGE, durable=True)

async def declare_reservation_finalization_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RESERVATION_FINALIZATION_RETRY_QUEUE, 
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": RESERVATION_EXCHANGE,
            "x-dead-letter-routing-key": RESERVATION_FINALIZATION_REDELIVERY_ROUTING_KEY,
        }
    )

async def bind_reservation_finalization_retry_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, RESERVATION_FINALIZATION_RETRY_ROUTING_KEY)
