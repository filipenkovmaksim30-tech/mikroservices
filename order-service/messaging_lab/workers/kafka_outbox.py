import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.db.models.kafka_outbox import KafkaOutboxEvent
from messaging_lab.messaging.contracts import AnalyticsEventEnvelope, OrderCreatedAnalyticsV1
from messaging_lab.messaging.kafka import KafkaEventProducer
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository

logger = logging.getLogger(__name__)


class KafkaOutboxPublisher:
    def __init__(
        self,
        session: AsyncSession,
        kafka_outbox_repository: KafkaOutboxRepository,
        kafka_producer: KafkaEventProducer,
        topic: str,
        batch_size: int = 100,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._session = session
        self._kafka_outbox_repository = kafka_outbox_repository
        self._kafka_producer = kafka_producer
        self._topic = topic
        self._batch_size = batch_size

    def _serialize_event(self, event: KafkaOutboxEvent) -> bytes:
        payload = OrderCreatedAnalyticsV1.model_validate(event.payload)
        envelope = AnalyticsEventEnvelope[OrderCreatedAnalyticsV1](
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            occurred_at=event.occurred_at,
            correlation_id=event.aggregate_id,
            payload=payload,
        )
        return envelope.model_dump_json().encode("utf-8")

    async def publish_batch(self) -> int:
        async with self._session.begin():
            events = await self._kafka_outbox_repository.get_unpublished_batch(self._batch_size)
            for event in events:
                body = self._serialize_event(event)
                key = str(event.aggregate_id).encode("utf-8")
                await self._kafka_producer.publish(topic=self._topic, key=key, value=body)
                await self._kafka_outbox_repository.mark_as_published(
                    event=event, published_at=datetime.now(UTC)
                )
            return len(events)


class KafkaOutboxWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        kafka_producer: KafkaEventProducer,
        topic: str,
        batch_size: int,
        outbox_poll_interval_seconds: float,
    ) -> None:

        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if outbox_poll_interval_seconds <= 0:
            raise ValueError("outbox_poll_interval_seconds must be positive")

        self._session_factory = session_factory
        self._kafka_producer = kafka_producer
        self._topic = topic
        self._batch_size = batch_size
        self._outbox_poll_interval_seconds = outbox_poll_interval_seconds

    async def run(self) -> None:
        while True:
            try:
                async with self._session_factory() as session:
                    kafka_outbox_repository = KafkaOutboxRepository(session)
                    kafka_outbox_publisher = KafkaOutboxPublisher(
                        session=session,
                        kafka_outbox_repository=kafka_outbox_repository,
                        kafka_producer=self._kafka_producer,
                        topic=self._topic,
                        batch_size=self._batch_size,
                    )
                    published_count = await kafka_outbox_publisher.publish_batch()
            except asyncio.CancelledError:
                logger.info("Kafka Outbox worker cancellation requested")
                raise
            except Exception:
                logger.exception(
                    "Kafka Outbox batch failed; retrying in %.2f seconds",
                    self._outbox_poll_interval_seconds,
                )
                await asyncio.sleep(self._outbox_poll_interval_seconds)
                continue

            if published_count == 0:
                await asyncio.sleep(self._outbox_poll_interval_seconds)
