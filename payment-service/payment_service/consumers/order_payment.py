import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_service.exceptions import PaymentRequestConflictError
from payment_service.messaging.contracts import PaymentRequestedEnvelope
from payment_service.messaging.rabbitmq.publisher import publish_message
from payment_service.messaging.rabbitmq.topology.payment_commands import (
    PAYMENT_COMMANDS_RETRY_ROUTING_KEY,
)
from payment_service.repositories.inbox import InboxRepository
from payment_service.repositories.payments import PaymentRepository
from payment_service.services.payment_processing import PaymentProcessingService

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3


async def retry_or_send_to_dlq(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    retry_routing_key: str,
    event_id: str,
    correlation_id: str,
) -> None:
    raw_retry_count = (
        message.headers.get("x-retry-count", 0)
        if message.headers
        else 0
    )
    try:
        retry_count = int(raw_retry_count)
        if retry_count < 0:
            raise ValueError
    except (TypeError, UnicodeDecodeError, ValueError):
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


async def handle_payment_requested(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        event = PaymentRequestedEnvelope.model_validate_json(message.body)
    except ValidationError:
        logger.error(
            "message.validation_failed",
            extra={"message_id": message.message_id},
        )
        await message.reject(requeue=False)
        return
    except Exception:
        logger.exception("message.parse_failed", extra={"message_id": message.message_id})
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session:
            inbox_repository = InboxRepository(session)
            payment_repository = PaymentRepository(session)
            service = PaymentProcessingService(
                session=session,
                inbox_repository=inbox_repository,
                payment_repository=payment_repository,
                consumer_name=consumer_name,
            )
            processed = await service.process(event)

    except PaymentRequestConflictError:
        logger.error(
            "message.rejected_business_error",
            extra={"event_id": event.event_id, "order_id": event.payload.order_id},
        )
        await message.reject(requeue=False)
        return

    except (SQLAlchemyError, OSError):
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_COMMANDS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_COMMANDS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    await message.ack()
    logger.info(
        "payment.request_recorded" if processed else "message.duplicate",
        extra={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "order_id": event.payload.order_id,
        },
    )
