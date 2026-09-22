import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage

from catalog_service.messaging.rabbitmq.publisher import publish_message

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


async def retry_or_send_to_dlq(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    retry_routing_key: str,
    event_id: str,
    correlation_id: str,
) -> None:
    raw_retry_count = message.headers.get("x-retry-count", 0) if message.headers else 0
    try:
        retry_count = int(raw_retry_count)
        if retry_count < 0:
            raise ValueError()
    except (TypeError, ValueError, UnicodeDecodeError):
        logger.error(
            "Invalid retry header: message_id=%s value=%r",
            message.message_id,
            raw_retry_count,
        )
        await message.reject(requeue=False)
        return

    if retry_count >= MAX_RETRY_ATTEMPTS:
        logger.error(
            "Retry attempts exhausted: message_id=%s retry_count=%s",
            message.message_id,
            retry_count,
        )
        await message.reject(requeue=False)
        return

    next_retry_count = retry_count + 1

    try:
        await publish_message(
            exchange=retry_exchange,
            routing_key=retry_routing_key,
            body=message.body,
            message_id=event_id,
            correlation_id=correlation_id,
            headers={"x-retry-count": next_retry_count},
        )
    except Exception:
        logger.exception(
            "Failed to publish catalog message to retry queue: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    await message.ack()
