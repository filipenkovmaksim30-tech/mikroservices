import logging
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage
from pydantic import TypeAdapter, ValidationError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from messaging_lab.messaging.contracts.stock_reservations import StockReservationResultEnvelopeV1
from messaging_lab.services.reservation_result import StockReservationResultService
from messaging_lab.exceptions import PermanentStockReservationResultError
from messaging_lab.messaging.rabbitmq.topology.reservation_result import RESERVATION_RESULTS_RETRY_ROUTING_KEY
from messaging_lab.exceptions import OrderNotFoundError
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.messaging.rabbitmq.publisher import publish_message

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3
STOCK_RESERVATION_ADAPTER = TypeAdapter(StockReservationResultEnvelopeV1)

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
    except (ValueError, TypeError, UnicodeDecodeError):
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

async def handler_stock_reservation_result(
    message: AbstractIncomingMessage,
    retry_exchange: AbstractExchange,
    consumer_name: str,
    session_factory: async_sessionmaker[AsyncSession]
) -> None:
    try:
        event = STOCK_RESERVATION_ADAPTER.validate_json(message.body)

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
            order_repository = OrderRepository(session)
            outbox_repository = RabbitMQOutboxRepository(session)
            service = StockReservationResultService(
                session=session,
                inbox_repository=inbox_repository,
                outbox_repository=outbox_repository,
                order_repository=order_repository,
                consumer_name=consumer_name,
            )
            processed = await service.process(event=event)

    except PermanentStockReservationResultError:
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
            retry_routing_key=RESERVATION_RESULTS_RETRY_ROUTING_KEY,
            event_id=str(event.event_id),
            correlation_id=str(event.correlation_id)
        )
        return

    except Exception:
        logger.exception("message.processing_retry", extra={"event_id": event.event_id})
        await retry_or_send_to_dlq(
            message=message,
            retry_exchange=retry_exchange,
            retry_routing_key=RESERVATION_RESULTS_RETRY_ROUTING_KEY,
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
                "pending_payment" if event.event_type == "stock.reserved" else "stock_failed"
            ) if processed else None,
        },
    )
