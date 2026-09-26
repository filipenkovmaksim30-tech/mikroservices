import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from catalog_service.consumers.retry_or_send_to_dlq import retry_or_send_to_dlq
from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationRequestedEnvelopeV1,
)
from catalog_service.messaging.rabbitmq.topology.reservation_commands import (
    RESERVATION_REQUEST_RETRY_ROUTING_KEY,
)
from catalog_service.repositories.inbox import InboxRepository
from catalog_service.repositories.outbox import RabbitMQOutboxRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.repositories.reservation import StockReservationRepository
from catalog_service.services.reservation import StockReservationService

logger = logging.getLogger(__name__)


async def handle_reservation_requested(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
    retry_exchange: AbstractExchange,
    consumer_name: str,
) -> None:
    try:
        event = StockReservationRequestedEnvelopeV1.model_validate_json(message.body)

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
            product_repository = ProductRepository(session)
            reservation_repository = StockReservationRepository(session)
            outbox_repository = RabbitMQOutboxRepository(session)
            inbox_repository = InboxRepository(session)
            service = StockReservationService(
                session=session,
                product_repository=product_repository,
                reservation_repository=reservation_repository,
                outbox_repository=outbox_repository,
                inbox_repository=inbox_repository,
                consumer_name=consumer_name,
            )

            processed = await service.process(event)

    except (SQLAlchemyError, OSError):
        logger.warning("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_REQUEST_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_REQUEST_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    await message.ack()
    logger.info(
        "message.processed" if processed else "message.duplicate",
        extra={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "order_id": event.payload.order_id,
        },
    )
