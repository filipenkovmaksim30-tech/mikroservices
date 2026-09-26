from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from messaging_lab.db.models.order import Order, OrderStatus
from messaging_lab.messaging.contracts.payments import (
    PaymentFailedEnvelope,
    PaymentFailedV1,
    PaymentSucceededEnvelope,
    PaymentSucceededV1,
)
from messaging_lab.messaging.contracts.stock_reservations import (
    StockReservedEnvelopeV1,
    StockReservedV1,
    StockReservationFailedEnvelopeV1,
    StockReservationFailedV1,
)
from messaging_lab.services.payment_result import PaymentResultService
from messaging_lab.services.reservation_result import StockReservationResultService
from tests.helpers import TrackingSession


def order_with_status(status: OrderStatus) -> Order:
    return Order(
        id=uuid4(),
        customer_id=uuid4(),
        receipt_email="buyer@example.com",
        total_amount=Decimal("100.00"),
        status=status,
        items=[],
    )


def stock_reserved_event(order_id: object) -> StockReservedEnvelopeV1:
    return StockReservedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=StockReservedV1(
            reservation_id=uuid4(), order_id=order_id, reserved_at=datetime.now(UTC)
        ),
    )


async def test_stock_reservation_starts_payment_only_once() -> None:
    order = order_with_status(OrderStatus.PENDING_STOCK)
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(side_effect=[True, False]))

    async def mark_pending_payment(_order: Order) -> None:
        _order.status = OrderStatus.PENDING_PAYMENT

    orders = SimpleNamespace(
        get_by_id_for_update=AsyncMock(return_value=order),
        mark_pending_payment=AsyncMock(side_effect=mark_pending_payment),
    )
    outbox = SimpleNamespace(add=AsyncMock())
    service = StockReservationResultService(session, inbox, orders, outbox, "stock-results")
    event = stock_reserved_event(order.id)

    assert await service.process(event) is True
    assert await service.process(event) is False

    assert order.status is OrderStatus.PENDING_PAYMENT
    assert session.started_transactions == 2
    orders.mark_pending_payment.assert_awaited_once_with(order)
    outbox.add.assert_awaited_once()
    payment_request = outbox.add.await_args.args[0]
    assert payment_request.event_type == "payment.requested"
    assert payment_request.payload["order_id"] == str(order.id)
    assert payment_request.payload["amount"] == "100.00"


async def test_successful_payment_emits_confirmation_analytics_and_notification() -> None:
    order = order_with_status(OrderStatus.PENDING_PAYMENT)
    completed_at = datetime.now(UTC)
    event = PaymentSucceededEnvelope(
        event_id=uuid4(),
        occurred_at=completed_at,
        correlation_id=order.id,
        payload=PaymentSucceededV1(
            payment_id=uuid4(),
            order_id=order.id,
            amount=order.total_amount,
            currency="RUB",
            completed_at=completed_at,
        ),
    )
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=True))

    async def mark_paid(order: Order) -> None:
        order.status = OrderStatus.PAID

    orders = SimpleNamespace(
        get_by_id_for_update=AsyncMock(return_value=order),
        mark_paid=AsyncMock(side_effect=mark_paid),
    )
    rabbit_outbox = SimpleNamespace(add=AsyncMock())
    kafka_outbox = SimpleNamespace(add=AsyncMock())
    service = PaymentResultService(
        session, inbox, rabbit_outbox, kafka_outbox, orders, "payment-results"
    )

    assert await service.process(event) is True

    assert order.status is OrderStatus.PAID
    assert session.started_transactions == 1
    assert rabbit_outbox.add.await_count == 2
    assert [call.args[0].event_type for call in rabbit_outbox.add.await_args_list] == [
        "stock.reservation.confirm.requested",
        "order.paid",
    ]
    kafka_outbox.add.assert_awaited_once()
    assert kafka_outbox.add.await_args.args[0].event_type == "order.paid"


async def test_failed_payment_releases_stock_and_emits_notifications() -> None:
    order = order_with_status(OrderStatus.PENDING_PAYMENT)
    completed_at = datetime.now(UTC)
    event = PaymentFailedEnvelope(
        event_id=uuid4(),
        occurred_at=completed_at,
        correlation_id=order.id,
        payload=PaymentFailedV1(
            payment_id=uuid4(),
            order_id=order.id,
            amount=order.total_amount,
            currency="RUB",
            failure_code="payment_declined",
            completed_at=completed_at,
        ),
    )
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=True))

    async def mark_payment_failed(order: Order) -> None:
        order.status = OrderStatus.PAYMENT_FAILED

    orders = SimpleNamespace(
        get_by_id_for_update=AsyncMock(return_value=order),
        mark_payment_failed=AsyncMock(side_effect=mark_payment_failed),
    )
    rabbit_outbox = SimpleNamespace(add=AsyncMock())
    kafka_outbox = SimpleNamespace(add=AsyncMock())
    service = PaymentResultService(
        session, inbox, rabbit_outbox, kafka_outbox, orders, "payment-results"
    )

    assert await service.process(event) is True

    assert order.status is OrderStatus.PAYMENT_FAILED
    assert [call.args[0].event_type for call in rabbit_outbox.add.await_args_list] == [
        "stock.reservation.release.requested",
        "order.payment_failed",
    ]
    kafka_outbox.add.assert_awaited_once()
    assert kafka_outbox.add.await_args.args[0].event_type == "order.payment_failed"


async def test_failed_stock_reservation_does_not_request_payment() -> None:
    order = order_with_status(OrderStatus.PENDING_STOCK)
    now = datetime.now(UTC)
    event = StockReservationFailedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=now,
        correlation_id=order.id,
        payload=StockReservationFailedV1(
            order_id=order.id,
            failure_code="insufficient_stock",
            failed_product_ids={uuid4()},
            failed_at=now,
        ),
    )
    session = TrackingSession()
    inbox = SimpleNamespace(try_add=AsyncMock(return_value=True))

    async def mark_stock_failed(target: Order) -> None:
        target.status = OrderStatus.STOCK_FAILED

    orders = SimpleNamespace(
        get_by_id_for_update=AsyncMock(return_value=order),
        mark_stock_failed=AsyncMock(side_effect=mark_stock_failed),
    )
    outbox = SimpleNamespace(add=AsyncMock())
    service = StockReservationResultService(
        session, inbox, orders, outbox, "stock-results"
    )

    assert await service.process(event) is True

    assert order.status is OrderStatus.STOCK_FAILED
    orders.mark_stock_failed.assert_awaited_once_with(order)
    outbox.add.assert_not_awaited()