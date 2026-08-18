

import asyncio
import logging
from datetime import UTC, datetime

from aio_pika.abc import AbstractExchange
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.db.models.rabbitmq_outbox import RabbitMQOutboxEvent
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.messaging.contracts import PaymentRequestedV1, PaymentRequestedEnvelope


logger = logging.getLogger(__name__)


class RabbitMQOutboxPublisher:
    def __init__(
        self,
        session: AsyncSession,
        outbox_repository: RabbitMQOutboxRepository,
        exchange: AbstractExchange,
        batch_size: int = 100,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self._session = session
        self._outbox_repository = outbox_repository
        self._exchange = exchange
        self._batch_size = batch_size

    def _serialize_event(self, event: RabbitMQOutboxEvent) -> bytes:
        payload = PaymentRequestedV1.model_validate(event.payload)
        envelope = PaymentRequestedEnvelope(
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
            events = await self._outbox_repository.get_unpublished_batch(self._batch_size)
            for event in events:
                body = self._serialize_event(event)

                await publish_message(
                    exchange=self._exchange,
                    routing_key=event.event_type,
                    body=body,
                    message_id=str(event.event_id),
                    correlation_id=str(event.aggregate_id),
                )
                await self._outbox_repository.mark_as_published(event, datetime.now(UTC))
            return len(events)


class RabbitMQOutboxWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        exchange: AbstractExchange,
        batch_size: int,
        outbox_poll_interval_seconds: float,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if outbox_poll_interval_seconds <= 0:
            raise ValueError("outbox_poll_interval_seconds must be positive")

        self._session_factory = session_factory
        self._exchange = exchange
        self._batch_size = batch_size
        self._outbox_poll_interval_seconds = outbox_poll_interval_seconds

    async def run(self) -> None:
        while True:
            try:
                async with self._session_factory() as session:
                    outbox_repository = RabbitMQOutboxRepository(session)
                    outbox_publisher = RabbitMQOutboxPublisher(
                        session=session,
                        outbox_repository=outbox_repository,
                        exchange=self._exchange,
                        batch_size=self._batch_size,
                    )
                    published_count = await outbox_publisher.publish_batch()
            except asyncio.CancelledError:
                logger.info("RabbitMQ Outbox worker cancellation requested")
                raise
            except Exception:
                logger.exception(
                    "RabbitMQ Outbox batch failed; retrying in %.2f seconds",
                    self._outbox_poll_interval_seconds,
                )
                await asyncio.sleep(self._outbox_poll_interval_seconds)
                continue

            if published_count == 0:
                await asyncio.sleep(self._outbox_poll_interval_seconds)
