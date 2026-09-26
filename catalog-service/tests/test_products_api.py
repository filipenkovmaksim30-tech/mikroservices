from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from catalog_service.api import app
from catalog_service.db.models.products import Product
from catalog_service.routers.dependencies import (
    get_current_principal,
    get_product_service,
    get_token_verifier,
)


@pytest.fixture
def isolated_app():
    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


def product() -> Product:
    return Product(
        id=uuid4(),
        category="books",
        name="Test book",
        description=None,
        price=Decimal("100.00"),
        stock_quantity=5,
        is_active=True,
    )


async def test_public_batch_returns_product_snapshot(isolated_app: object) -> None:
    item = product()
    service = SimpleNamespace(get_products_by_ids=AsyncMock(return_value=[item]))
    app.dependency_overrides[get_product_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/products/batch", json={"product_ids": [str(item.id)]})

    assert response.status_code == 200
    assert response.json()["products"][0]["id"] == str(item.id)
    assert response.json()["products"][0]["stock_quantity"] == 5
    service.get_products_by_ids.assert_awaited_once_with(product_ids={item.id})


async def test_admin_product_create_requires_token(isolated_app: object) -> None:
    app.dependency_overrides[get_token_verifier] = lambda: object()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/admin/products",
            json={"category": "books", "name": "Test", "price": "100.00", "stock_quantity": 5},
        )

    assert response.status_code == 401


async def test_non_admin_cannot_create_product(isolated_app: object) -> None:
    app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(role="customer")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/admin/products",
            json={"category": "books", "name": "Test", "price": "100.00", "stock_quantity": 5},
        )

    assert response.status_code == 403


async def test_admin_can_create_product(isolated_app: object) -> None:
    item = product()
    service = SimpleNamespace(create_product=AsyncMock(return_value=item))
    app.dependency_overrides[get_current_principal] = lambda: SimpleNamespace(role="admin")
    app.dependency_overrides[get_product_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/admin/products",
            json={"category": "books", "name": "Test book", "price": "100.00", "stock_quantity": 5},
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(item.id)
    service.create_product.assert_awaited_once()
