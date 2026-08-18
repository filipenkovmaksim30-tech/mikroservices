from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


ORDER_EVENTS_EXCHANGE = "orders.events"
NOTIFICATIONS_ORDER_CREATED_QUEUE = "notifications.order_created"
ORDER_CREATED_ROUTING_KEY = "order.created"

ORDER_REDELIVERY_EXCHANGE = "notifications.redelivery"
ORDER_REDELIVERY_ROUTING_KEY = "order.redelivery"

DEAD_LETTER_EXCHANGE = "orders.dlx"
DEAD_LETTER_QUEUE = "notifications.order_created.dlq"
ORDER_DLQ_ROUTING_KEY = "order.created.dead"

RETRY_LETTER_EXCHANGE = "orders.retry"
RETRY_LETTER_QUEUE = "notifications.order_created.retry"
ORDER_RETRY_ROUTING_KEY = "order.created.retry"


async def declare_order_events_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        ORDER_EVENTS_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )


async def declare_notifications_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        NOTIFICATIONS_ORDER_CREATED_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": ORDER_DLQ_ROUTING_KEY,
        },
    )


async def bind_notifications_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=ORDER_CREATED_ROUTING_KEY)


async def declare_redelivery_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        ORDER_REDELIVERY_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def bind_redelivery_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=ORDER_REDELIVERY_ROUTING_KEY)


async def declare_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(DEAD_LETTER_QUEUE, durable=True)


async def bind_dlq(dlx: AbstractExchange, dlq: AbstractQueue) -> None:
    await dlq.bind(dlx, routing_key=ORDER_DLQ_ROUTING_KEY)


async def declare_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        RETRY_LETTER_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        RETRY_LETTER_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": ORDER_REDELIVERY_EXCHANGE,
            "x-dead-letter-routing-key": ORDER_REDELIVERY_ROUTING_KEY,
        },
    )


async def bind_retry_queue(
    retry_exchange: AbstractExchange,
    retry_queue: AbstractQueue,
) -> None:
    await retry_queue.bind(retry_exchange, routing_key=ORDER_RETRY_ROUTING_KEY)
