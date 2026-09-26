import logging

from aiokafka import AIOKafkaProducer
from aiokafka.structs import ConsumerRecord

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from analytics_service.messaging.contract import (
    AnalyticsEventEnvelope,
    AnalyticsOrderEnvelope,
)

from analytics_service.db.session import async_session_factory
from analytics_service.config import Settings
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.repositories.processed_event import ProcessedEventRepository
from analytics_service.services.order_created import OrderCreatedAnalyticsService
from analytics_service.services.order_payment import AnalyticPaymentService
from analytics_service.messaging.kafka_dlq import publish_to_dlq
from analytics_service.exceptions import PermanentAnalyticsEventError

ANALYTICS_ORDER_ADAPTER = TypeAdapter(AnalyticsOrderEnvelope)
logger = logging.getLogger(__name__)


async def process_message(
    message: ConsumerRecord,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
) -> bool:
    event = ANALYTICS_ORDER_ADAPTER.validate_json(message.value)

    async with session_factory() as session:
        analytics_order_repository = AnalyticsOrderRepository(session)
        processed_event_repository = ProcessedEventRepository(session)

        if isinstance(event, AnalyticsEventEnvelope):

            analytics_service = OrderCreatedAnalyticsService(
                session=session,
                analytics_order_repository=analytics_order_repository,
                processed_event_repository=processed_event_repository,
                consumer_name=consumer_name,
            )

            processed = await analytics_service.process(event)
        else:
            analytics_payment_service = AnalyticPaymentService(
                session,
                processed_repository=processed_event_repository,
                analytics_order_repository=analytics_order_repository,
                consumer_name=consumer_name
            )
            processed = await analytics_payment_service.process(event)
        logger.info(
            "message.processed" if processed else "message.duplicate",
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "order_id": event.payload.order_id,
                "topic": getattr(message, "topic", None),
                "partition": getattr(message, "partition", None),
                "offset": getattr(message, "offset", None),
            },
        )
        return processed

async def handle_message(
    message: ConsumerRecord,
    dlq_producer: AIOKafkaProducer,
    settings: Settings,
) -> None:
    try:
        await process_message(
            message=message,
            session_factory=async_session_factory,
            consumer_name=settings.kafka_consumer_group,
        )
    except ValidationError:
        await publish_to_dlq(
            producer=dlq_producer,
            dlq_topic=settings.kafka_analytics_dlq_topic,
            message=message,
            error_type="validation_error"
        )
        logger.warning(
            "message.dlq_published",
            extra={
                "topic": getattr(message, "topic", None),
                "partition": getattr(message, "partition", None),
                "offset": getattr(message, "offset", None),
            },
        )
    except PermanentAnalyticsEventError as exc:
        await publish_to_dlq(
            producer=dlq_producer,
            dlq_topic=settings.kafka_analytics_dlq_topic,
            message=message,
            error_type=type(exc).__name__,
        )
        logger.warning(
            "message.dlq_published",
            extra={
                "topic": getattr(message, "topic", None),
                "partition": getattr(message, "partition", None),
                "offset": getattr(message, "offset", None),
            },
        )
    # TODO: publish OrderNotFoundError to a retry topic with retry count and delayed reprocessing. bug №11:
