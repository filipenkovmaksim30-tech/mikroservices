from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from messaging_lab.api import app
from messaging_lab.db.models.order import Order, OrderStatus
from messaging_lab.routers.dependencies import (
    get_current_principal,
    get_order_service,
    get_token_verifier,
)


@pytest.fixture
def isolated_app():
    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


def saved_order(customer_id: object) -> Order:
    return Order(
        id=uuid4(),
        customer_id=customer_id,
        receipt_email="buyer@example.com",
        total_amount=Decimal("100.00"),
        status=OrderStatus.PENDING_STOCK,
        created_at=datetime.now(UTC),
        items=[],
    )


async def test_customer_list_is_scoped_to_authenticated_customer(isolated_app: object) -> None:
    customer_id = uuid4()
    order = saved_order(customer_id)
    service = SimpleNamespace(get_orders_by_customer=AsyncMock(return_value=[order]))
    app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(
        sub=customer_id, role="customer"
    )
    app.dependency_overrides[get_order_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/orders/my?limit=5&offset=10")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(order.id)
    service.get_orders_by_customer.assert_awaited_once_with(
        customer_id=customer_id, limit=5, offset=10
    )


async def test_non_admin_cannot_read_admin_order(isolated_app: object) -> None:
    app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(
        sub=uuid4(), role="customer"
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/admin/orders/{uuid4()}")

    assert response.status_code == 403


async def test_missing_token_returns_401(isolated_app: object) -> None:
    app.dependency_overrides[get_token_verifier] = lambda: object()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/orders/my")

    assert response.status_code == 401
