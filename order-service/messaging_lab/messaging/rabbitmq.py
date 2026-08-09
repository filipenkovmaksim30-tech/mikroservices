import aio_pika
from aio_pika import DeliveryMode, ExchangeType
from aio_pika.abc import AbstractQueue, AbstractRobustConnection, AbstractChannel, AbstractExchange


PAYMENT_COMMANDS_EXCHANGE = "payments.commands"
PAYMENT_REQUESTED_QUEUE = "payments.payment_requested"
PAYMENT_REQUESTED_ROUTING_KEY = "payment.requested"

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


######################################

ANALYTICS_ORDERS_QUEUE = "analytics.orders"
ANALYTICS_ORDERS_PATTERN = "order.*"

AUDIT_EVENTS_QUEUE = "audit.all_events"
AUDIT_EVENTS_PATTERN = "#"

SYSTEM_BROADCAST_EXCHANGE = "system.broadcast"
CACHE_INVALIDATION_QUEUE = "cache.invalidation"
WEBSOCKET_UPDATES_QUEUE = "websocket.updates"

###############################################

async def connect_rabbitmq(url: str) -> AbstractRobustConnection:
    return await aio_pika.connect_robust(url, timeout=10)

async def create_channel(connection: AbstractRobustConnection) -> AbstractChannel:
    return await connection.channel(publisher_confirms=True, on_return_raises=True)


async def declare_payments_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(PAYMENT_COMMANDS_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def declare_payments_queue(channel: AbstractChannel) -> AbstractQueue:
    return await channel.declare_queue(PAYMENT_REQUESTED_QUEUE, durable=True)

async def bind_payments_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=PAYMENT_REQUESTED_ROUTING_KEY)

async def declare_events_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(ORDER_EVENTS_EXCHANGE, ExchangeType.TOPIC, durable=True)

async def declare_notifications_queue(channel: AbstractChannel) -> AbstractQueue:
    queue: AbstractQueue = await channel.declare_queue(
        NOTIFICATIONS_ORDER_CREATED_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": ORDER_DLQ_ROUTING_KEY
        }
    )
    return queue
    
async def bind_notifications_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=ORDER_CREATED_ROUTING_KEY)


async def declare_redelivery_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(ORDER_REDELIVERY_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def bind_redelivery_queue(exchange: AbstractExchange, queue: AbstractQueue) -> None:
    await queue.bind(exchange, routing_key=ORDER_REDELIVERY_ROUTING_KEY)



async def declare_dlx(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(DEAD_LETTER_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def declare_dlq(channel: AbstractChannel) -> AbstractQueue:
    queue: AbstractQueue = await channel.declare_queue(DEAD_LETTER_QUEUE, durable=True)
    return queue

async def bind_dlq(dlx: AbstractExchange, dlq: AbstractQueue) -> None:
    await dlq.bind(dlx, routing_key=ORDER_DLQ_ROUTING_KEY)



async def declare_retry_exchange(channel: AbstractChannel) -> AbstractExchange:
    return await channel.declare_exchange(RETRY_LETTER_EXCHANGE, ExchangeType.DIRECT, durable=True)

async def declare_retry_queue(channel: AbstractChannel) -> AbstractQueue:
    queue: AbstractQueue = await channel.declare_queue(
        RETRY_LETTER_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 5000,
            "x-dead-letter-exchange": ORDER_REDELIVERY_EXCHANGE,
            "x-dead-letter-routing-key": ORDER_REDELIVERY_ROUTING_KEY
        }
    )
    return queue

async def bind_retry_queue(retry_exchange: AbstractExchange, retry_queue: AbstractQueue) -> None:
    await retry_queue.bind(retry_exchange, routing_key=ORDER_RETRY_ROUTING_KEY)



async def declare_analytics_queue(channel: AbstractChannel) -> AbstractQueue:
    analytics_queue: AbstractQueue = await channel.declare_queue(ANALYTICS_ORDERS_QUEUE, durable=True)
    return analytics_queue

async def bind_analytics_queue(exchange: AbstractExchange, analytics_queue: AbstractQueue) -> None:
    await analytics_queue.bind(exchange, routing_key=ANALYTICS_ORDERS_PATTERN)

async def declare_audit_queue(channel: AbstractChannel) -> AbstractQueue:
    audit_queue: AbstractQueue = await channel.declare_queue(AUDIT_EVENTS_QUEUE, durable=True)
    return audit_queue

async def bind_audit_queue(exchange: AbstractExchange, audit_queue: AbstractQueue) -> None:
    await audit_queue.bind(exchange, routing_key=AUDIT_EVENTS_PATTERN)




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


