import aio_pika
from aio_pika import ExchangeType, DeliveryMode
from aio_pika.abc import AbstractQueue, AbstractRobustConnection, AbstractChannel, AbstractExchange


PAYMENT_COMMANDS_EXCHANGE = "payments.commands"
PAYMENT_ORDER_QUEUE = "payments.payment_requested"
PAYMENT_ORDER_ROUTING_KEY = "payment.requested"

async def connect_rabbitmq(url: str) -> AbstractRobustConnection:
    return await aio_pika.connect_robust(url, timeout=10)

async def declare_channel(connection: AbstractRobustConnection) -> AbstractChannel:
    return await connection.channel(publisher_confirms=True, on_return_raises=True)

async def declare_payments_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_COMMANDS_EXCHANGE, ExchangeType.DIRECT, durable=True)


async def declare_payments_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_ORDER_QUEUE, durable=True)

async def bind_payments_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_ORDER_ROUTING_KEY)


async def publish_message(
    exchange: AbstractExchange,
    routing_key: str,
    body: bytes,
    message_id: str,
    correlation_id: str,
    headers: dict[str, int] | None = None
) -> None:
    message = aio_pika.Message(
        body=body,
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=message_id,
        correlation_id=correlation_id,
        headers=headers
)

    await exchange.publish(message, routing_key, mandatory=True)

