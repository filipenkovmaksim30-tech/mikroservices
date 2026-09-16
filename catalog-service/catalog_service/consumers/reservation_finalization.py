import logging

from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from catalog_service.messaging.rabbitmq.topology.reservation_finalization import RESERVATION_FINALIZATION_RETRY_ROUTING_KEY
from catalog_service.messaging.contracts.stock_reservations import StockReservationFinalizationEnvelopeV1
from catalog_service.repositories.inbox import InboxRepository
from catalog_service.repositories.reservation import StockReservationRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.services.reservation_finalization import StockReservationFinalizationService

from catalog_service.consumers.retry_or_send_to_dlq import retry_or_send_to_dlq
from catalog_service.exceptions import PermanentStockReservationFinalizationError

logger =  logging.getLogger(__name__)

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
        logger.exception(
            "Permanent validation reservation finalization error: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    try:
        async with session_factory() as session: 
            inbox_repository = InboxRepository(session)
            reservation_repository = StockReservationRepository(session)
            product_repository= ProductRepository(session)
            service = StockReservationFinalizationService(
                session=session,
                inbox_repository=inbox_repository,
                reservation_repository=reservation_repository,
                product_repository=product_repository,
                consumer_name=consumer_name,
            )

            await service.process(event)

    except (SQLAlchemyError, OSError):
        await retry_or_send_to_dlq(
            message=message, 
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_FINALIZATION_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id)
        )
        return

    except PermanentStockReservationFinalizationError:
        logger.exception(
            "Permanent reservation finalization error: message_id=%s",
            message.message_id,
        )
        await message.reject(requeue=False)
        return

    except Exception:
        logger.exception(
            "Unexpected stock reservation finalization processing error: message_id=%s",
            message.message_id,
        )
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_FINALIZATION_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id),
        )
        return
    
    await message.ack()