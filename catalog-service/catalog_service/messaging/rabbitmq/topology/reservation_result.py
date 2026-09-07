from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange, AbstractChannel


RESERVATION_EVENT_EXCHANGE = "stock.reservation.events"
RESERVATION_RESULT_QUEUE = "orders.reservation.reservation_result"
RESERVATION_RESULT_SUCCEEDED_ROUTING_KEY = "stock.reserved"
RESERVATION_RESULT_FAILED_ROUTING_KEY = "stock.reservation.failed"


async def declare_reservation_result_exchange(channel: AbstractChannel) -> AbstractExchange:

    return await channel.declare_exchange(RESERVATION_EVENT_EXCHANGE, ExchangeType.DIRECT, durable=True)
