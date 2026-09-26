import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from messaging_lab.workers import kafka_outbox, rabbitmq_outbox
from tests.helpers import TrackingSession


def event(event_type: str, *, channel: str = "rabbitmq") -> SimpleNamespace:
    order_id, customer_id, product_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    base = {"order_id": str(order_id)}
    payloads = {
        "stock.reservation.requested": {
            **base, "items": [{"product_id": str(product_id), "quantity": 2}],
        },
        "payment.requested": {**base, "amount": "100.00", "currency": "RUB"},
        "stock.reservation.confirm.requested": base,
        "stock.reservation.release.requested": base,
        "order.paid": {
            **base, "customer_id": str(customer_id), "receipt_email": "buyer@example.com",
            "total_amount": "100.00", "currency": "RUB", "paid_at": now.isoformat(),
        },
        "order.payment_failed": {
            **base, "customer_id": str(customer_id), "receipt_email": "buyer@example.com",
            "total_amount": "100.00", "currency": "RUB", "failed_at": now.isoformat(),
            "failure_code": "card_declined",
        },
        "order.created": {
            **base, "customer_id": str(customer_id), "total_amount": "100.00",
            "items": [{"product_id": str(product_id), "quantity": 2, "unit_price": "50.00"}],
        },
    }
    payload = payloads[event_type].copy()
    if event_type in {"order.paid", "order.payment_failed"}:
        payload.pop("customer_id" if channel == "rabbitmq" else "receipt_email")
    return SimpleNamespace(
        event_id=uuid4(), aggregate_id=order_id, event_type=event_type,
        event_version=1, occurred_at=now, payload=payload,
    )


@pytest.mark.parametrize(
    "event_type",
    [
        "stock.reservation.requested", "payment.requested",
        "stock.reservation.confirm.requested", "stock.reservation.release.requested",
        "order.paid", "order.payment_failed",
    ],
)
def test_rabbitmq_outbox_serializes_each_supported_event(event_type: str) -> None:
    publisher = rabbitmq_outbox.RabbitMQOutboxPublisher(
        TrackingSession(), object(), {event_type: object()}
    )

    envelope = json.loads(publisher._serialize_event(event(event_type)))

    assert envelope["event_type"] == event_type
    assert envelope["payload"]["order_id"] == envelope["correlation_id"]


@pytest.mark.parametrize("event_type", ["order.created", "order.paid", "order.payment_failed"])
def test_kafka_outbox_serializes_each_supported_event(event_type: str) -> None:
    publisher = kafka_outbox.KafkaOutboxPublisher(
        TrackingSession(), object(), object(), "orders.analytics.v1"
    )

    envelope = json.loads(publisher._serialize_event(event(event_type, channel="kafka")))

    assert envelope["event_type"] == event_type
    assert envelope["payload"]["order_id"] == envelope["correlation_id"]


async def test_rabbitmq_outbox_marks_published_only_after_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = event("payment.requested")
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[item]),
        mark_as_published=AsyncMock(),
    )
    publish = AsyncMock()
    monkeypatch.setattr(rabbitmq_outbox, "publish_message", publish)
    publisher = rabbitmq_outbox.RabbitMQOutboxPublisher(
        TrackingSession(), repository, {item.event_type: object()}
    )

    assert await publisher.publish_batch() == 1
    assert publish.await_args.kwargs["routing_key"] == "payment.requested"
    repository.mark_as_published.assert_awaited_once()


async def test_rabbitmq_publish_failure_keeps_outbox_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = event("payment.requested")
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[item]),
        mark_as_published=AsyncMock(),
    )
    monkeypatch.setattr(
        rabbitmq_outbox, "publish_message", AsyncMock(side_effect=OSError("broker down"))
    )
    publisher = rabbitmq_outbox.RabbitMQOutboxPublisher(
        TrackingSession(), repository, {item.event_type: object()}
    )

    with pytest.raises(OSError, match="broker down"):
        await publisher.publish_batch()

    repository.mark_as_published.assert_not_awaited()


async def test_kafka_outbox_marks_published_only_after_send() -> None:
    item = event("order.created", channel="kafka")
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[item]),
        mark_as_published=AsyncMock(),
    )
    producer = SimpleNamespace(publish=AsyncMock())
    publisher = kafka_outbox.KafkaOutboxPublisher(
        TrackingSession(), repository, producer, "orders.analytics.v1"
    )

    assert await publisher.publish_batch() == 1
    assert producer.publish.await_args.kwargs["key"] == str(item.aggregate_id).encode()
    repository.mark_as_published.assert_awaited_once()


async def test_kafka_publish_failure_keeps_outbox_pending() -> None:
    item = event("order.created", channel="kafka")
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[item]),
        mark_as_published=AsyncMock(),
    )
    producer = SimpleNamespace(publish=AsyncMock(side_effect=OSError("Kafka down")))
    publisher = kafka_outbox.KafkaOutboxPublisher(
        TrackingSession(), repository, producer, "orders.analytics.v1"
    )

    with pytest.raises(OSError, match="Kafka down"):
        await publisher.publish_batch()

    repository.mark_as_published.assert_not_awaited()
