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
            "Failed to publish payment message to retry queue: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    await message.ack()


async def handle_payment_requested(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        event = PaymentRequestedEnvelope.model_validate_json(message.body)
    except ValidationError as exc:
        logger.error(
            "Permanent message validation error: message_id=%s errors=%s",
            message.message_id,
            exc.error_count(),
        )
        await message.reject(requeue=False)
        return
    except Exception:
        logger.exception(
            "Unexpected payment message parsing error: message_id=%s",
            message.message_id,
        )
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
            await service.process(event)

    except PaymentRequestConflictError as exc:
        logger.error(
            "Payment request conflict: message_id=%s error=%s",
            message.message_id,
            exc,
        )
        await message.reject(requeue=False)
        return

    except (SQLAlchemyError, OSError):
        logger.exception(
            "Temporary order payment error: message_id=%s",
            message.message_id,
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_COMMANDS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    except Exception:
        logger.exception(
            "Unexpected order payment error: message_id=%s",
            message.message_id,
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_COMMANDS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    await message.ack()
