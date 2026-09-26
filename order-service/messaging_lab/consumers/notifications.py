import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.messaging.contracts.notifications import OrderNotificationEnvelopeV1
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.messaging.rabbitmq.topology.notifications import (
    ORDER_NOTIFICATIONS_RETRY_ROUTING_KEY,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.services.notifications import (
    NotificationService,
    PermanentNotificationError,
    TransientNotificationError,
)

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3
NOTIFICATIONS_CONSUMER = "order-service.notifications.v1"
NOTIFICATION_EVENT_ADAPTER = TypeAdapter(OrderNotificationEnvelopeV1)


async def retry_or_send_to_dlq(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    event: OrderNotificationEnvelopeV1,
    retry_count: int,
) -> None:
    if retry_count >= MAX_RETRY_ATTEMPTS:
        logger.error(
            "message.rejected_retry_exhausted",
            extra={"event_id": event.event_id, "retry_count": retry_count},
        )
        await message.reject(requeue=False)
        return

    next_retry_count = retry_count + 1

    try:
        await publish_message(
            exchange=retry_exchange,
            routing_key=ORDER_NOTIFICATIONS_RETRY_ROUTING_KEY,
            body=message.body,
            message_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
            headers={"x-retry-count": next_retry_count},
        )
    except Exception:
        logger.exception(
            "message.retry_publish_failed",
            extra={"event_id": event.event_id},
        )
        await message.reject(requeue=False)
        return

    await message.ack()
    logger.warning(
        "message.retry_scheduled",
        extra={"event_id": event.event_id, "retry_count": next_retry_count},
    )


async def process_with_inbox(
    event: OrderNotificationEnvelopeV1,
    notification_service: NotificationService,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    async with session_factory() as session, session.begin():
        repository = InboxRepository(session)
        is_new = await repository.try_add(
            consumer_name=NOTIFICATIONS_CONSUMER,
            event_id=event.event_id,
            event_type=event.event_type,
        )

        if not is_new:
            return False

        await notification_service.process_notification(event=event)

    return True


async def handle_notification(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    notification_service: NotificationService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        event = NOTIFICATION_EVENT_ADAPTER.validate_json(message.body)
    except ValidationError:
        logger.error("message.validation_failed", extra={"message_id": message.message_id})

        await message.reject(requeue=False)
        return
    except Exception:
        logger.exception("message.parse_failed", extra={"message_id": message.message_id})
        await message.reject(requeue=False)
        return

    raw_retry_count = message.headers.get("x-retry-count", 0) if message.headers else 0
    try:
        retry_count = int(raw_retry_count)
        if retry_count < 0:
            raise ValueError
    except (ValueError, TypeError, UnicodeDecodeError):
        logger.error(
            "message.rejected_invalid_retry",
            extra={"event_id": event.event_id, "message_id": message.message_id},
        )
        await message.reject(requeue=False)
        return

    try:
        processed = await process_with_inbox(
            event=event,
            notification_service=notification_service,
            session_factory=session_factory,
        )

        if not processed:
            logger.info("message.duplicate", extra={"event_id": event.event_id})
        else:
            logger.info(
                "notification.sent",
                extra={
                    "event_type": event.event_type,
                    "event_id": event.event_id,
                    "order_id": event.payload.order_id,
                },
            )
    except PermanentNotificationError:
        logger.error(
            "message.rejected_business_error",
            extra={"event_id": event.event_id, "order_id": event.payload.order_id},
        )
        await message.reject(requeue=False)
        return
    except TransientNotificationError:
        logger.warning(
            "message.processing_retry",
            extra={"event_id": event.event_id},
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            event=event,
            retry_count=retry_count,
        )
        return
    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            event=event,
            retry_count=retry_count,
        )
        return

    await message.ack()
