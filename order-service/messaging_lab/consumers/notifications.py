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
            "Notification retries exhausted: event_id=%s retry_count=%s",
            event.event_id,
            retry_count,
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
            "Failed to publish notification to retry queue: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    await message.ack()
    logger.info(
        "Notification scheduled for retry: event_id=%s retry_count=%s",
        event.event_id,
        next_retry_count,
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
    except ValidationError as exc:
        logger.warning(
            "Permanent notification validation error: message_id=%s errors=%s",
            message.message_id,
            exc.error_count(),
        )

        await message.reject(requeue=False)
        return
    except Exception:
        logger.exception(
            "Unexpected notification message parsing error: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    raw_retry_count = message.headers.get("x-retry-count", 0) if message.headers else 0
    try:
        retry_count = int(raw_retry_count)
        if retry_count < 0:
            raise ValueError
    except (ValueError, TypeError, UnicodeDecodeError):
        logger.error(
            "Invalid retry header: message_id=%s value=%r",
            message.message_id,
            raw_retry_count,
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
            logger.info("Duplicate notification skipped: event_id=%s", event.event_id)
        else:
            logger.info(
                "Notification sent: event_type=%s event_id=%s order_id=%s",
                event.event_type,
                event.event_id,
                event.payload.order_id,
            )
    except PermanentNotificationError as exc:
        logger.error("Permanent notification error: event_id=%s error=%s", event.event_id, exc)
        await message.reject(requeue=False)
        return
    except TransientNotificationError as exc:
        logger.warning(
            "Transient notification error: event_id=%s error=%s",
            event.event_id,
            exc,
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            event=event,
            retry_count=retry_count,
        )
        return
    except Exception:
        logger.exception(
            "Unexpected notification processing error: message_id=%s",
            message.message_id,
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            event=event,
            retry_count=retry_count,
        )
        return

    await message.ack()
