from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.messaging.rabbitmq.topology.notifications import ORDER_RETRY_ROUTING_KEY
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.schemas.event import EventEnvelope, OrderCreatedV1
from messaging_lab.services.notifications import (
    NotificationService,
    PermanentNotificationError,
    TransientNotificationError,
)


MAX_RETRY_ATTEMPTS = 3
NOTIFICATIONS_CONSUMER = "notifications"



async def process_with_inbox(
    event: EventEnvelope[OrderCreatedV1],
    notification_service: NotificationService,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            repository = InboxRepository(session)
            is_new = await repository.try_add(
                consumer_name=NOTIFICATIONS_CONSUMER,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            await notification_service.process_order_created(event=event)

    return True

async def handle_order_created(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    notification_service: NotificationService,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        event = EventEnvelope[OrderCreatedV1].model_validate_json(message.body)
    except ValidationError as exc:
        print(
            "Permanent message validation error:",
            f"message_id={message.message_id}",
            f"errors={exc.error_count()}",
        )

        await message.reject(requeue=False)
        return

    raw_retry_count = (
        message.headers.get("x-retry-count", 0)
        if message.headers
        else 0
    )
    retry_count = int(raw_retry_count)

    try:
        processed = await process_with_inbox(
            event=event,
            notification_service=notification_service,
            session_factory=session_factory,
        )

        if not processed:
            print(
                "Duplicate message skipped:",
                f"event_id={event.event_id}",
            )
        else:
            print(
                "Order confirmation sent:",
                f"event_id={event.event_id}",
                f"order_id={event.payload.order_id}",
                f"receipt_email={event.payload.receipt_email}",
            )
    except PermanentNotificationError as exc:
        print(
            "Permanent notification error:",
            f"event_id={event.event_id}",
            f"error={exc}",
        )
        await message.reject(requeue=False)
        return
    except TransientNotificationError as exc:
        if retry_count >= MAX_RETRY_ATTEMPTS:
            print(
                "Retry attempts exhausted:",
                f"event_id={event.event_id}",
                f"retry_count={retry_count}",
                f"error={exc}",
            )

            await message.reject(requeue=False)
            return

        next_retry_count = retry_count + 1

        await publish_message(
            exchange=retry_exchange,
            routing_key=ORDER_RETRY_ROUTING_KEY,
            body=message.body,
            message_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
            headers={
                "x-retry-count": next_retry_count,
            },
        )

        await message.ack()

        print(
            "Message scheduled for retry:",
            f"event_id={event.event_id}",
            f"retry_count={next_retry_count}",
        )
        return

    await message.ack()
