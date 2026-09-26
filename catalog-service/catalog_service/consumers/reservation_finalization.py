import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from catalog_service.consumers.retry_or_send_to_dlq import retry_or_send_to_dlq
from catalog_service.exceptions import PermanentStockReservationFinalizationError
from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationFinalizationEnvelopeV1,
)
from catalog_service.messaging.rabbitmq.topology.reservation_finalization import (
    RESERVATION_FINALIZATION_RETRY_ROUTING_KEY,
)
from catalog_service.repositories.inbox import InboxRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.repositories.reservation import StockReservationRepository
from catalog_service.services.reservation_finalization import StockReservationFinalizationService

logger = logging.getLogger(__name__)

STOCK_FINALIZATION_ADAPTER = TypeAdapter(StockReservationFinalizationEnvelopeV1)


async def handle_finalization_requested(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker[AsyncSession],
    retry_exchange: AbstractExchange,
    consumer_name: str,
) -> None:
    try:
        event = STOCK_FINALIZATION_ADAPTER.validate_json(message.body)

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
            reservation_repository = StockReservationRepository(session)
            product_repository = ProductRepository(session)
            service = StockReservationFinalizationService(
                session=session,
                inbox_repository=inbox_repository,
                reservation_repository=reservation_repository,
                product_repository=product_repository,
                consumer_name=consumer_name,
            )

            processed = await service.process(event)

    except PermanentStockReservationFinalizationError:
        logger.error(
            "message.rejected_business_error",
            extra={"event_id": event.event_id, "order_id": event.payload.order_id},
        )
        await message.reject(requeue=False)
        return

    except (SQLAlchemyError, OSError):
        logger.warning("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_FINALIZATION_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_FINALIZATION_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return

    await message.ack()
    logger.info(
        "reservation.status_changed" if processed else "message.duplicate",
        extra={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "order_id": event.payload.order_id,
            "target_status": (
                "confirmed"
                if event.event_type == "stock.reservation.confirm.requested"
                else "released"
            ) if processed else None,
        },
    )
