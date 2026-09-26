from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from payment_service.db.models.payments import Payment, PaymentStatus
from payment_service.services.payment_execute import PaymentExecuteService
from payment_service.services.payment_provider import PaymentResult
from tests.helpers import TrackingSession


def pending_payment() -> Payment:
    return Payment(
        id=uuid4(),
        order_id=uuid4(),
        amount=Decimal("100.00"),
        currency="RUB",
        status=PaymentStatus.PENDING,
    )


async def test_successful_charge_is_outside_transaction_and_writes_outbox() -> None:
    payment = pending_payment()
    session = TrackingSession()

    async def claim(*, processing_token: object, **_kwargs: object) -> Payment:
        assert session.active_transactions == 1
        payment.status = PaymentStatus.PROCESSING
        payment.processing_token = processing_token
        return payment

    async def charge(**kwargs: object) -> PaymentResult:
        assert session.active_transactions == 0
        assert kwargs["idempotency_key"] == payment.id
        assert kwargs["order_id"] == payment.order_id
        return PaymentResult(succeeded=True)

    async def mark_succeeded(*, completed_at: datetime, **_kwargs: object) -> Payment:
        payment.status = PaymentStatus.SUCCEEDED
        payment.completed_at = completed_at
        return payment

    payments = SimpleNamespace(
        claim_for_processing=AsyncMock(side_effect=claim),
        get_by_id_for_update=AsyncMock(return_value=payment),
        mark_succeeded=AsyncMock(side_effect=mark_succeeded),
        mark_failed=AsyncMock(),
    )
    outbox = SimpleNamespace(add=AsyncMock())
    provider = SimpleNamespace(charge=AsyncMock(side_effect=charge))
    service = PaymentExecuteService(session, outbox, payments, provider, 30)

    assert await service.execute(payment.id) is True

    assert session.started_transactions == 2
    assert session.active_transactions == 0
    payments.mark_succeeded.assert_awaited_once()
    payments.mark_failed.assert_not_awaited()
    outbox.add.assert_awaited_once()
    event = outbox.add.await_args.args[0]
    assert event.event_type == "payment.succeeded"
    assert event.aggregate_id == payment.id
    assert event.correlation_id == payment.order_id
    assert event.payload["payment_id"] == str(payment.id)
    assert event.payload["order_id"] == str(payment.order_id)


async def test_unclaimable_payment_never_calls_provider() -> None:
    payment = pending_payment()
    session = TrackingSession()
    payments = SimpleNamespace(claim_for_processing=AsyncMock(return_value=None))
    outbox = SimpleNamespace(add=AsyncMock())
    provider = SimpleNamespace(charge=AsyncMock())
    service = PaymentExecuteService(session, outbox, payments, provider, 30)

    assert await service.execute(payment.id) is False

    assert session.started_transactions == 1
    provider.charge.assert_not_awaited()
    outbox.add.assert_not_awaited()


async def test_stale_worker_cannot_finalize_payment() -> None:
    payment = pending_payment()
    session = TrackingSession()

    async def claim(*, processing_token: object, **_kwargs: object) -> Payment:
        payment.status = PaymentStatus.PROCESSING
        payment.processing_token = processing_token
        return payment

    async def charge(**_kwargs: object) -> PaymentResult:
        # Another worker took over this payment while the provider was busy.
        payment.processing_token = uuid4()
        return PaymentResult(succeeded=True)

    payments = SimpleNamespace(
        claim_for_processing=AsyncMock(side_effect=claim),
        get_by_id_for_update=AsyncMock(return_value=payment),
        mark_succeeded=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    outbox = SimpleNamespace(add=AsyncMock())
    provider = SimpleNamespace(charge=AsyncMock(side_effect=charge))
    service = PaymentExecuteService(session, outbox, payments, provider, 30)

    assert await service.execute(payment.id) is False

    assert session.started_transactions == 2
    payments.mark_succeeded.assert_not_awaited()
    payments.mark_failed.assert_not_awaited()
    outbox.add.assert_not_awaited()
