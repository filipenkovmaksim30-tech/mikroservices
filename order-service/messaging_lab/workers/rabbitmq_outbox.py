import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from aio_pika.abc import AbstractExchange
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging_lab.db.models.rabbitmq_outbox import RabbitMQOutboxEvent
from messaging_lab.messaging.contracts.payments import (
    PaymentRequestedEnvelope,
    PaymentRequestedV1,
)
from messaging_lab.messaging.contracts.notifications import (
    OrderPaidV1,
    OrderPaidEnvelopeV1,
    OrderPaymentFailedV1,
    OrderPaymentFailedEnvelopeV1,
)
from messaging_lab.messaging.contracts.stock_reservations import (
    StockReservationRequestedEnvelopeV1,
    StockReservationRequestedV1,
    StockReservationConfirmRequestedV1,
    StockReservationConfirmRequestedEnvelopeV1,
    StockReservationReleaseRequestedV1,
    StockReservationReleaseRequestedEnvelopeV1,
)
from messaging_lab.messaging.rabbitmq.publisher import publish_message
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository

logger = logging.getLogger(__name__)


class RabbitMQOutboxPublisher:
    def __init__(
        self,
        session: AsyncSession,
        outbox_repository: RabbitMQOutboxRepository,
        exchanges_by_event_type: Mapping[str, AbstractExchange],
        batch_size: int = 100,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self._session = session
        self._outbox_repository = outbox_repository
        self._exchanges_by_event_type = dict(exchanges_by_event_type)
        self._batch_size = batch_size

    def _serialize_event(self, event: RabbitMQOutboxEvent) -> bytes:
        match event.event_type:
            case "stock.reservation.requested":
                payload = StockReservationRequestedV1.model_validate(event.payload)
                envelope = StockReservationRequestedEnvelopeV1(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.aggregate_id,
                    payload=payload,
                )
                return envelope.model_dump_json().encode("utf-8")

            case "payment.requested":
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

            case "stock.reservation.confirm.requested":
                payload = StockReservationConfirmRequestedV1.model_validate(event.payload)
                envelope = StockReservationConfirmRequestedEnvelopeV1(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.aggregate_id,
                    payload=payload
                )
                return envelope.model_dump_json().encode("utf-8")

            case "stock.reservation.release.requested":
                payload = StockReservationReleaseRequestedV1.model_validate(event.payload)
                envelope = StockReservationReleaseRequestedEnvelopeV1(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.aggregate_id,
                    payload=payload
                )
                return envelope.model_dump_json().encode("utf-8")

            case "order.paid":
                payload = OrderPaidV1.model_validate(event.payload)
                envelope = OrderPaidEnvelopeV1(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.aggregate_id,
                    payload=payload,
                )
                return envelope.model_dump_json().encode("utf-8")

            case "order.payment_failed":
                payload = OrderPaymentFailedV1.model_validate(event.payload)
                envelope = OrderPaymentFailedEnvelopeV1(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.aggregate_id,
                    payload=payload,
                )
                return envelope.model_dump_json().encode("utf-8")

            case unsupported_event_type:
                raise ValueError(
                    f"Unsupported RabbitMQ outbox event type: {unsupported_event_type}"
                )

    async def publish_batch(self) -> int:
        async with self._session.begin():
            events = await self._outbox_repository.get_unpublished_batch(self._batch_size)
            for event in events:
                body = self._serialize_event(event)

                exchange = self._exchanges_by_event_type.get(event.event_type)
                if exchange is None:
                    raise ValueError(
                        f"No RabbitMQ exchange configured for event type: {event.event_type}"
                    )

                await publish_message(
                    exchange=exchange,
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
        exchanges_by_event_type: Mapping[str, AbstractExchange],
        batch_size: int,
        outbox_poll_interval_seconds: float,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if outbox_poll_interval_seconds <= 0:
            raise ValueError("outbox_poll_interval_seconds must be positive")

        self._session_factory = session_factory
        self._exchanges_by_event_type = dict(exchanges_by_event_type)
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
                        exchanges_by_event_type=self._exchanges_by_event_type,
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
