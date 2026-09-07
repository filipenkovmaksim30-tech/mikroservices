import aio_pika
from aio_pika.abc import AbstractExchange

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
        headers=headers,
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        correlation_id=correlation_id,
        message_id=message_id
    )
    
    await exchange.publish(message, routing_key, mandatory=True)