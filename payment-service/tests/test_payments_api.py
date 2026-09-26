from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from payment_service.api import app
from payment_service.db.models.payments import Payment, PaymentStatus
from payment_service.exceptions import PaymentNotFoundError
from payment_service.routers.dependencies import (
    get_current_principal,
    get_payment_service,
    get_token_verifier,
    require_admin,
)


@pytest.fixture
def isolated_app() -> object:
    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


def payment_response_object() -> Payment:
    return Payment(
        id=uuid4(),
        order_id=uuid4(),
        amount=Decimal("100.00"),
        currency="RUB",
        status=PaymentStatus.PENDING,
        failure_code=None,
        created_at=datetime.now(UTC),
        completed_at=None,
    )


async def test_admin_can_read_payment_by_id(isolated_app: object) -> None:
    payment = payment_response_object()
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=payment))
    app.dependency_overrides[require_admin] = lambda: None
    app.dependency_overrides[get_payment_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/admin/payments/{payment.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(payment.id)
    assert response.json()["failure_code"] is None
    assert response.json()["completed_at"] is None
    assert "processing_token" not in response.json()
    service.get_by_id.assert_awaited_once_with(payment.id)


async def test_admin_can_find_payment_by_order_id(isolated_app: object) -> None:
    payment = payment_response_object()
    service = SimpleNamespace(get_by_order_id=AsyncMock(return_value=payment))
    app.dependency_overrides[require_admin] = lambda: None
    app.dependency_overrides[get_payment_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/admin/payments/by-order/{payment.order_id}")

    assert response.status_code == 200
    assert response.json()["order_id"] == str(payment.order_id)
    service.get_by_order_id.assert_awaited_once_with(payment.order_id)


async def test_payment_list_passes_filter_and_pagination(isolated_app: object) -> None:
    service = SimpleNamespace(get_payments=AsyncMock(return_value=[]))
    app.dependency_overrides[require_admin] = lambda: None
    app.dependency_overrides[get_payment_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/admin/payments?status=succeeded&limit=5&offset=10")
        invalid = await client.get("/admin/payments?status=unknown")

    assert response.status_code == 200
    assert response.json() == []
    service.get_payments.assert_awaited_once_with(PaymentStatus.SUCCEEDED, 5, 10)
    assert invalid.status_code == 422


async def test_missing_payment_returns_404(isolated_app: object) -> None:
    payment_id = uuid4()
    service = SimpleNamespace(get_by_id=AsyncMock(side_effect=PaymentNotFoundError(payment_id)))
    app.dependency_overrides[require_admin] = lambda: None
    app.dependency_overrides[get_payment_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/admin/payments/{payment_id}")

    assert response.status_code == 404


async def test_missing_token_returns_401(isolated_app: object) -> None:
    app.dependency_overrides[get_token_verifier] = lambda: object()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/admin/payments")

    assert response.status_code == 401


async def test_non_admin_returns_403(isolated_app: object) -> None:
    app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(role="user")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/admin/payments")

    assert response.status_code == 403
