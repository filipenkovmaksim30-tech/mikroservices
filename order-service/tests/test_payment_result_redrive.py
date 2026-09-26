from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from messaging_lab.db.models.order import OrderStatus
from messaging_lab.messaging.contracts.payments import (
    PaymentFailedEnvelope,
    PaymentFailedV1,
    PaymentSucceededEnvelope,
    PaymentSucceededV1,
)
from messaging_lab.services.payment_result_redrive import (
    PaymentResultRedriveService,
    RedriveStatus,
)


def result_event(*, succeeded: bool):
    order_id = uuid4()
    now = datetime.now(UTC)
    if succeeded:
        payload = PaymentSucceededV1(
            payment_id=uuid4(), order_id=order_id, amount=Decimal("100.00"),
            currency="RUB", completed_at=now,
        )
        return PaymentSucceededEnvelope(
            event_id=uuid4(), occurred_at=now, correlation_id=order_id, payload=payload
        )
    payload = PaymentFailedV1(
        payment_id=uuid4(), order_id=order_id, amount=Decimal("100.00"),
        currency="RUB", completed_at=now, failure_code="declined",
    )
    return PaymentFailedEnvelope(
        event_id=uuid4(), occurred_at=now, correlation_id=order_id, payload=payload
    )


@pytest.mark.parametrize(
    ("succeeded", "order_status", "expected"),
    [
        (True, OrderStatus.PENDING_PAYMENT, RedriveStatus.READY),
        (True, OrderStatus.PAID, RedriveStatus.ALREADY_PROCESSED),
        (True, OrderStatus.PAYMENT_FAILED, RedriveStatus.CONFLICT),
        (False, OrderStatus.PENDING_PAYMENT, RedriveStatus.READY),
        (False, OrderStatus.PAYMENT_FAILED, RedriveStatus.ALREADY_PROCESSED),
        (False, OrderStatus.PAID, RedriveStatus.CONFLICT),
    ],
)
async def test_redrive_decision_matches_order_status(
    succeeded: bool, order_status: OrderStatus, expected: RedriveStatus
) -> None:
    event = result_event(succeeded=succeeded)
    order = SimpleNamespace(total_amount=Decimal("100.00"), status=order_status)
    orders = SimpleNamespace(get_by_id=AsyncMock(return_value=order))
    inbox = SimpleNamespace(exists=AsyncMock(return_value=False))
    service = PaymentResultRedriveService(orders, inbox, "payment-results")

    decision = await service.inspect(event)

    assert decision.status is expected
    inbox.exists.assert_awaited_once_with(
        consumer_name="payment-results", event_id=event.event_id
    )


async def test_redrive_refuses_missing_order_and_amount_mismatch() -> None:
    event = result_event(succeeded=True)
    orders = SimpleNamespace(get_by_id=AsyncMock(return_value=None))
    inbox = SimpleNamespace(exists=AsyncMock(return_value=False))
    service = PaymentResultRedriveService(orders, inbox, "payment-results")

    assert (await service.inspect(event)).status is RedriveStatus.CONFLICT
    orders.get_by_id.return_value = SimpleNamespace(
        total_amount=Decimal("200.00"), status=OrderStatus.PENDING_PAYMENT
    )
    assert (await service.inspect(event)).status is RedriveStatus.CONFLICT


async def test_redrive_skips_event_already_in_inbox() -> None:
    event = result_event(succeeded=True)
    orders = SimpleNamespace(get_by_id=AsyncMock())
    inbox = SimpleNamespace(exists=AsyncMock(return_value=True))
    service = PaymentResultRedriveService(orders, inbox, "payment-results")

    assert (await service.inspect(event)).status is RedriveStatus.ALREADY_PROCESSED
    orders.get_by_id.assert_not_awaited()
