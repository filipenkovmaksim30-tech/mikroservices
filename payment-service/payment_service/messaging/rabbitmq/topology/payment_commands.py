from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


PAYMENT_COMMANDS_EXCHANGE = "payments.commands"
PAYMENT_ORDER_QUEUE = "payments.payment_requested"
PAYMENT_ORDER_ROUTING_KEY = "payment.requested"


async def declare_payment_commands_exchange(
    channel: AbstractChannel,
) -> AbstractExchange:
    return await channel.declare_exchange(
        PAYMENT_COMMANDS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_payment_commands_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_ORDER_QUEUE, durable=True)


async def bind_payment_commands_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_ORDER_ROUTING_KEY)
