from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from payment_service.exceptions import PaymentRequestConflictError
from payment_service.messaging.contracts import PaymentRequestedEnvelope, PaymentRequestedV1
from payment_service.services.payment_processing import PaymentProcessingService
from tests.helpers import TrackingSession


def payment_requested_event(amount: Decimal = Decimal("100.00")) -> PaymentRequestedEnvelope:
    order_id = uuid4()
    return PaymentRequestedEnvelope(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=PaymentRequestedV1(order_id=order_id, amount=amount, currency="RUB"),
    )


async def test_new_command_creates_one_payment() -> None:
    event = payment_requested_event()
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=True))
    payments = SimpleNamespace(
        get_by_order_id=AsyncMock(return_value=None), add=AsyncMock()
    )
    service = PaymentProcessingService(session, payments, inbox, "payment-commands")

    assert await service.process(event) is True

    inbox.try_add.assert_awaited_once_with(
        consumer_name="payment-commands",
        event_id=event.event_id,
        event_type="payment.requested",
    )
    payment = payments.add.await_args.args[0]
    assert payment.order_id == event.payload.order_id
    assert payment.amount == event.payload.amount
    assert payment.currency == "RUB"
    assert session.started_transactions == 1
    assert session.active_transactions == 0


async def test_duplicate_event_does_not_create_another_payment() -> None:
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=False))
    payments = SimpleNamespace(get_by_order_id=AsyncMock(), add=AsyncMock())
    service = PaymentProcessingService(session, payments, inbox, "payment-commands")

    assert await service.process(payment_requested_event()) is False

    payments.get_by_order_id.assert_not_awaited()
    payments.add.assert_not_awaited()


async def test_same_order_with_different_amount_is_rejected() -> None:
    event = payment_requested_event(Decimal("200.00"))
    existing = SimpleNamespace(amount=Decimal("100.00"), currency="RUB")
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=True))
    payments = SimpleNamespace(
        get_by_order_id=AsyncMock(return_value=existing), add=AsyncMock()
    )
    service = PaymentProcessingService(session, payments, inbox, "payment-commands")

    with pytest.raises(PaymentRequestConflictError):
        await service.process(event)

    payments.add.assert_not_awaited()
    assert session.active_transactions == 0
