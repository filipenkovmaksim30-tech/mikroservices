from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange, AbstractChannel


PAYMENT_EVENTS_EXCHANGE = "payments.events"
PAYMENT_SUCCEEDED_ROUTING_KEY = "payment.succeeded"
PAYMENT_FAILED_ROUTING_KEY = "payment.failed"

async def declare_payment_events_exchange(channel: AbstractChannel) -> AbstractExchange:

    return await channel.declare_exchange(PAYMENT_EVENTS_EXCHANGE, ExchangeType.DIRECT, durable=True)
