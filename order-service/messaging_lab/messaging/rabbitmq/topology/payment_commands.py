from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange


PAYMENT_COMMANDS_EXCHANGE = "payments.commands"
PAYMENT_REQUESTED_QUEUE = "payments.payment_requested"
PAYMENT_REQUESTED_ROUTING_KEY = "payment.requested"


async def declare_payment_commands_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        PAYMENT_COMMANDS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )
