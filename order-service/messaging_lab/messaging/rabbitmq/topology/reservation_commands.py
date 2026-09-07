from aio_pika.abc import AbstractChannel, AbstractExchange
from aio_pika import ExchangeType

RESERVATION_EXCHANGE = "stock.reservation.commands"
RESERVATION_REQUEST_QUEUE = "stock.reservation.reservation_requested"
RESERVATION_REQUEST_ROUTING_KEY = "stock.reservation.requested"

async def declare_reservation_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RESERVATION_EXCHANGE, ExchangeType.DIRECT, durable=True)