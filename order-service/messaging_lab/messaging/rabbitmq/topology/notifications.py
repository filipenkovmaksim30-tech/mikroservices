from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


ORDER_EVENTS_EXCHANGE = "orders.events"
ORDER_NOTIFICATIONS_QUEUE = "order.notifications"
ORDER_FAILED_NOTIFICATION_ROUTING_KEY = "order.payment_failed"
ORDER_PAID_NOTIFICATION_ROUTING_KEY = "order.paid"

ORDER_NOTIFICATIONS_DLX = "orders.notifications.dlx"
ORDER_NOTIFICATIONS_DLQ = "order.notifications.dlq"
ORDER_NOTIFICATIONS_DLQ_ROUTING_KEY = "order.notifications.dead"

ORDER_NOTIFICATIONS_RETRY_EXCHANGE = "orders.notification.retry"
ORDER_NOTIFICATIONS_RETRY_QUEUE = "order.notifications.retry"
ORDER_NOTIFICATIONS_RETRY_ROUTING_KEY = "order.notifications.retry"
ORDER_NOTIFICATIONS_REDELIVERY_ROUTING_KEY = "order.notifications.redelivery"


async def declare_order_events_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        ORDER_EVENTS_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_notifications_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        ORDER_NOTIFICATIONS_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": ORDER_NOTIFICATIONS_DLX,
            "x-dead-letter-routing-key": ORDER_NOTIFICATIONS_DLQ_ROUTING_KEY,
        },
    )


async def bind_notifications_queue(
    exchange: AbstractExchange,
    queue: AbstractQueue,
) -> None:
    await queue.bind(exchange, routing_key=ORDER_FAILED_NOTIFICATION_ROUTING_KEY)
    await queue.bind(exchange, routing_key=ORDER_PAID_NOTIFICATION_ROUTING_KEY)
    await queue.bind(exchange, routing_key=ORDER_NOTIFICATIONS_REDELIVERY_ROUTING_KEY)


async def declare_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        ORDER_NOTIFICATIONS_DLX,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_dlq(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(ORDER_NOTIFICATIONS_DLQ, durable=True)


async def bind_dlq(dlx: AbstractExchange, dlq: AbstractQueue) -> None:
    await dlq.bind(dlx, routing_key=ORDER_NOTIFICATIONS_DLQ_ROUTING_KEY)


async def declare_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(
        ORDER_NOTIFICATIONS_RETRY_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )


async def declare_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(
        ORDER_NOTIFICATIONS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": ORDER_EVENTS_EXCHANGE,
            "x-dead-letter-routing-key": ORDER_NOTIFICATIONS_REDELIVERY_ROUTING_KEY,
        },
    )


async def bind_retry_queue(
    retry_exchange: AbstractExchange,
    retry_queue: AbstractQueue,
) -> None:
    await retry_queue.bind(retry_exchange, routing_key=ORDER_NOTIFICATIONS_RETRY_ROUTING_KEY)
