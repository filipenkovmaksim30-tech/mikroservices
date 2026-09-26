from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from payment_service.messaging.contracts import PaymentFailedV1, PaymentSucceededV1
from payment_service.workers import rabbitmq_outbox as worker_module
from tests.helpers import TrackingSession


def outbox_event(event_type: str) -> SimpleNamespace:
    payment_id, order_id = uuid4(), uuid4()
    payload = {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": Decimal("100.00"),
        "currency": "RUB",
        "completed_at": datetime.now(UTC),
    }
    if event_type == "payment.failed":
        payload["failure_code"] = "card_declined"
        payload = PaymentFailedV1.model_validate(payload).model_dump(mode="json")
    else:
        payload = PaymentSucceededV1.model_validate(payload).model_dump(mode="json")
    return SimpleNamespace(
        event_id=uuid4(), event_type=event_type, event_version=1,
        occurred_at=datetime.now(UTC), correlation_id=order_id, payload=payload,
    )


@pytest.mark.parametrize("event_type", ["payment.succeeded", "payment.failed"])
async def test_publisher_sends_valid_envelope_then_marks_published(
    monkeypatch: pytest.MonkeyPatch, event_type: str
) -> None:
    event = outbox_event(event_type)
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[event]),
        mark_as_published=AsyncMock(),
    )
    publish = AsyncMock()
    monkeypatch.setattr(worker_module, "publish_message", publish)
    session = TrackingSession()
    publisher = worker_module.RabbitMQOutboxPublisher(session, repository, object())

    assert await publisher.publish_batch() == 1

    assert publish.await_args.kwargs["routing_key"] == event_type
    assert event_type.encode() in publish.await_args.kwargs["body"]
    repository.mark_as_published.assert_awaited_once()
    assert session.active_transactions == 0


async def test_publish_failure_leaves_outbox_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    event = outbox_event("payment.succeeded")
    repository = SimpleNamespace(
        get_unpublished_batch=AsyncMock(return_value=[event]),
        mark_as_published=AsyncMock(),
    )
    monkeypatch.setattr(
        worker_module, "publish_message", AsyncMock(side_effect=OSError("broker down"))
    )
    publisher = worker_module.RabbitMQOutboxPublisher(TrackingSession(), repository, object())

    with pytest.raises(OSError, match="broker down"):
        await publisher.publish_batch()

    repository.mark_as_published.assert_not_awaited()


def test_unknown_event_type_is_rejected_before_publish() -> None:
    publisher = worker_module.RabbitMQOutboxPublisher(
        TrackingSession(), object(), object()
    )
    with pytest.raises(ValueError, match="Unsupported payment event type"):
        publisher._serialize_event(SimpleNamespace(event_type="payment.unknown"))
