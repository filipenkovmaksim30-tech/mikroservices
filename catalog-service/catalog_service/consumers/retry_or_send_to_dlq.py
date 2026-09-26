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
        await message.reject(requeue=False)
        logger.error(
            "message.rejected_invalid_retry",
            extra={"event_id": event_id, "message_id": message.message_id},
        )
        return

    if retry_count >= MAX_RETRY_ATTEMPTS:
        await message.reject(requeue=False)
        logger.error(
            "message.rejected_retry_exhausted",
            extra={"event_id": event_id, "retry_count": retry_count},
        )
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
        logger.exception("message.retry_publish_failed", extra={"event_id": event_id})
        await message.reject(requeue=False)
        return

    await message.ack()
    logger.warning(
        "message.retry_scheduled",
        extra={"event_id": event_id, "retry_count": next_retry_count},
    )
