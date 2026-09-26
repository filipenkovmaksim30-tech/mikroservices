from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from messaging_lab.db.models.order import Order, OrderStatus
from messaging_lab.exceptions import InsufficientProductStockError, OrderIdempotentConflictError
from messaging_lab.schemas.catalog import CatalogProductSnapshot
from messaging_lab.services.orders import CreateOrderItem, OrderService
from tests.helpers import TrackingSession


def dependencies() -> tuple[
    OrderService,
    TrackingSession,
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
]:
    session = TrackingSession()
    orders = SimpleNamespace(
        get_by_customer_id_idempotency_key=AsyncMock(return_value=None),
        add=AsyncMock(),
    )
    catalog = SimpleNamespace(get_products_by_ids=AsyncMock())
    rabbit_outbox = SimpleNamespace(add=AsyncMock())
    kafka_outbox = SimpleNamespace(add=AsyncMock())
    service = OrderService(session, orders, catalog, rabbit_outbox, kafka_outbox)
    return service, session, orders, catalog, rabbit_outbox, kafka_outbox


async def test_new_order_uses_catalog_snapshot_and_writes_two_outboxes() -> None:
    service, session, orders, catalog, rabbit_outbox, kafka_outbox = dependencies()
    product_id = uuid4()
    customer_id = uuid4()
    catalog.get_products_by_ids.return_value = [
        CatalogProductSnapshot(
            id=product_id, price=Decimal("125.50"), stock_quantity=5, is_active=True
        )
    ]

    async def add_order(order: Order) -> Order:
        assert session.active_transactions == 1
        order.id = uuid4()
        return order

    async def fetch_catalog(*, product_ids: set) -> list[CatalogProductSnapshot]:
        assert session.active_transactions == 0
        assert product_ids == {product_id}
        return catalog.get_products_by_ids.return_value

    orders.add.side_effect = add_order
    catalog.get_products_by_ids.side_effect = fetch_catalog

    created = await service.create_order(
        customer_id=customer_id,
        receipt_email="buyer@example.com",
        idempotency_key="request-1",
        items=[CreateOrderItem(product_id=product_id, quantity=2)],
    )

    assert created.status in (None, OrderStatus.PENDING_STOCK)
    assert created.total_amount == Decimal("251.00")
    assert created.items[0].unit_price == Decimal("125.50")
    assert created.items[0].quantity == 2
    assert session.started_transactions == 2
    assert session.active_transactions == 0
    rabbit_outbox.add.assert_awaited_once()
    kafka_outbox.add.assert_awaited_once()
    reservation_event = rabbit_outbox.add.await_args.args[0]
    analytics_event = kafka_outbox.add.await_args.args[0]
    assert reservation_event.event_type == "stock.reservation.requested"
    assert reservation_event.payload["order_id"] == str(created.id)
    assert analytics_event.event_type == "order.created"
    assert analytics_event.payload["total_amount"] == "251.00"


async def test_same_key_and_body_returns_existing_order_without_catalog_call() -> None:
    service, session, orders, catalog, rabbit_outbox, kafka_outbox = dependencies()
    product_id = uuid4()
    customer_id = uuid4()
    items = [CreateOrderItem(product_id=product_id, quantity=1)]
    existing = Order(
        id=uuid4(),
        customer_id=customer_id,
        idempotency_key="request-1",
        request_hash=service._calculate_request_hash("buyer@example.com", items),
        receipt_email="buyer@example.com",
        total_amount=Decimal("100.00"),
        items=[],
    )
    orders.get_by_customer_id_idempotency_key.return_value = existing

    result = await service.create_order(customer_id, "buyer@example.com", "request-1", items)

    assert result is existing
    assert session.started_transactions == 1
    catalog.get_products_by_ids.assert_not_awaited()
    orders.add.assert_not_awaited()
    rabbit_outbox.add.assert_not_awaited()
    kafka_outbox.add.assert_not_awaited()


async def test_same_key_with_different_body_is_conflict() -> None:
    service, _, orders, catalog, _, _ = dependencies()
    product_id = uuid4()
    customer_id = uuid4()
    orders.get_by_customer_id_idempotency_key.return_value = SimpleNamespace(
        request_hash="a-different-hash"
    )

    with pytest.raises(OrderIdempotentConflictError):
        await service.create_order(
            customer_id, "buyer@example.com", "request-1",
            [CreateOrderItem(product_id=product_id, quantity=1)],
        )

    catalog.get_products_by_ids.assert_not_awaited()


async def test_insufficient_catalog_stock_does_not_write_order() -> None:
    service, _, orders, catalog, rabbit_outbox, kafka_outbox = dependencies()
    product_id = uuid4()
    catalog.get_products_by_ids.return_value = [
        CatalogProductSnapshot(
            id=product_id, price=Decimal("100.00"), stock_quantity=1, is_active=True
        )
    ]

    with pytest.raises(InsufficientProductStockError):
        await service.create_order(
            uuid4(), "buyer@example.com", "request-1",
            [CreateOrderItem(product_id=product_id, quantity=2)],
        )

    orders.add.assert_not_awaited()
    rabbit_outbox.add.assert_not_awaited()
    kafka_outbox.add.assert_not_awaited()
