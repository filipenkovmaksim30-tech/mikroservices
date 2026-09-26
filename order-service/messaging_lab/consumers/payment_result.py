import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.exceptions import OrderNotFoundError, PermanentPaymentResultError
from messaging_lab.messaging.contracts.payments import PaymentResultEnvelope
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.messaging.rabbitmq.topology.payment_result import (
    PAYMENT_RESULTS_RETRY_ROUTING_KEY,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.services.payment_result import PaymentResultService

logger = logging.getLogger(__name__)

PAYMENT_RESULT_ADAPTER = TypeAdapter(PaymentResultEnvelope)


MAX_RETRY_ATTEMPTS  = 3

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
            headers={
                "x-retry-count": next_retry_count
            },
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

async def handler_payment_result(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession]
) -> None:
    try:
        event = PAYMENT_RESULT_ADAPTER.validate_json(message.body)

    except ValidationError:
        logger.error("message.validation_failed", extra={"message_id": message.message_id})
        await message.reject(requeue=False)
        return

    except Exception:
        logger.exception("message.parse_failed", extra={"message_id": message.message_id})
        await message.reject(requeue=False)
        return
    
    try:
        async with session_factory() as session:
            inbox_repository = InboxRepository(session)
            outbox_repository = RabbitMQOutboxRepository(session)
            kafka_outbox_repository = KafkaOutboxRepository(session)
            order_repository = OrderRepository(session)
            service = PaymentResultService(
                session=session,
                inbox_repository=inbox_repository,
                outbox_repository=outbox_repository,
                kafka_outbox_repository=kafka_outbox_repository,
                order_repository=order_repository,
                consumer_name=consumer_name,
            )

        
            processed = await service.process(event=event)

    except PermanentPaymentResultError:
        logger.error(
            "message.rejected_business_error",
            extra={"event_id": event.event_id, "order_id": event.payload.order_id},
        )
        await message.reject(requeue=False)
        return 

    except (OrderNotFoundError, SQLAlchemyError, OSError):
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_RESULTS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id)
        )
        return

    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=PAYMENT_RESULTS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    await message.ack()
    logger.info(
        "order.status_changed" if processed else "message.duplicate",
        extra={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "order_id": event.payload.order_id,
            "target_status": (
                "paid" if event.event_type == "payment.succeeded" else "payment_failed"
            ) if processed else None,
        },
    )
