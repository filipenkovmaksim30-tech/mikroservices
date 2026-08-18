from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue


ANALYTICS_ORDERS_QUEUE = "analytics.orders"
ANALYTICS_ORDERS_PATTERN = "order.*"

AUDIT_EVENTS_QUEUE = "audit.all_events"
AUDIT_EVENTS_PATTERN = "#"

SYSTEM_BROADCAST_EXCHANGE = "system.broadcast"
CACHE_INVALIDATION_QUEUE = "cache.invalidation"
WEBSOCKET_UPDATES_QUEUE = "websocket.updates"


async def declare_analytics_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(ANALYTICS_ORDERS_QUEUE, durable=True)


async def bind_analytics_queue(
    exchange: AbstractExchange,
    analytics_queue: AbstractQueue,
) -> None:
    await analytics_queue.bind(exchange, routing_key=ANALYTICS_ORDERS_PATTERN)


async def declare_audit_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(AUDIT_EVENTS_QUEUE, durable=True)


async def bind_audit_queue(
    exchange: AbstractExchange,
    audit_queue: AbstractQueue,
) -> None:
    await audit_queue.bind(exchange, routing_key=AUDIT_EVENTS_PATTERN)
