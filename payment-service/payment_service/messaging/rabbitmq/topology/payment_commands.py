from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


PAYMENT_COMMANDS_EXCHANGE = "payments.commands"
PAYMENT_ORDER_QUEUE = "payments.payment_requested"
PAYMENT_ORDER_ROUTING_KEY = "payment.requested"


PAYMENT_DLX = "payments.dlx"
PAYMENT_COMMANDS_DLQ = "payments.payment_requested.dlq"
PAYMENT_DLQ_ROUTING_KEY = "payment.requested.dead"

PAYMENT_COMMANDS_RETRY_EXCHANGE = "payments.commands.retry"
PAYMENT_COMMANDS_RETRY_QUEUE = "payments.payment_requested.retry"
PAYMENT_COMMANDS_RETRY_ROUTING_KEY = "payment.requested.retry"


async def declare_payment_commands_exchange(
    channel: AbstractChannel,
) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_COMMANDS_EXCHANGE, ExchangeType.DIRECT, durable=True)


async def declare_payment_commands_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        PAYMENT_ORDER_QUEUE, 
        durable=True,
        arguments={
            "x-dead-letter-exchange": PAYMENT_DLX,
            "x-dead-letter-routing-key": PAYMENT_DLQ_ROUTING_KEY,
        },
    )


async def bind_payment_commands_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_ORDER_ROUTING_KEY)


async def declare_payment_commands_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_DLX, ExchangeType.DIRECT, durable=True)

async def declare_payment_commands_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_COMMANDS_DLQ, durable=True)

async def bind_payment_commands_dlq(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_DLQ_ROUTING_KEY)


async def declare_payment_commands_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_COMMANDS_RETRY_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def declare_payment_commands_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        PAYMENT_COMMANDS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": PAYMENT_COMMANDS_EXCHANGE,
            "x-dead-letter-routing-key": PAYMENT_ORDER_ROUTING_KEY,
        },
    )

async def bind_payment_commands_retry_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_COMMANDS_RETRY_ROUTING_KEY)
