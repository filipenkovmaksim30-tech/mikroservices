from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_catalog_list_forwards_pagination(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.get("/api/products", params={"limit": 7, "offset": 3})

    assert response.status_code == 200
    assert str(requests[0].url) == "http://catalog.test/products?offset=3&limit=7"


async def test_login_forwards_form_and_set_cookie(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.post(
        "/api/auth/token", data={"username": "buyer@example.com", "password": "password12345"}
    )

    assert response.status_code == 200
    assert requests[0].url.path == "/auth/token"
    assert b"username=buyer%40example.com" in requests[0].content
    assert "password12345" in requests[0].content.decode()
    assert "refresh_token=secret" in response.headers["set-cookie"]


async def test_refresh_forwards_cookie_and_returns_rotated_cookie(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    client.cookies.set("refresh_token", "original", domain="gateway.test", path="/api/auth")
    response = await client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert requests[0].headers["cookie"] == "refresh_token=original"
    assert "refresh_token=rotated" in response.headers["set-cookie"]


async def test_my_orders_requires_access_token_before_upstream(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.get("/api/orders/my")

    assert response.status_code == 401
    assert requests == []


async def test_my_orders_forwards_bearer_and_pagination(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.get(
        "/api/orders/my", params={"limit": 5, "offset": 10},
        headers={"Authorization": "Bearer signed-token"},
    )

    assert response.status_code == 200
    assert requests[0].headers["authorization"] == "Bearer signed-token"
    assert dict(requests[0].url.params) == {"limit": "5", "offset": "10"}


async def test_admin_payment_rejects_non_admin_before_upstream(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    from api_gateway.main import app
    from api_gateway.routers.dependencies import get_token_verifier

    client, requests = gateway
    app.dependency_overrides[get_token_verifier]().decode_access_token.return_value.role = "user"
    response = await client.get(
        f"/api/admin/payments/{uuid4()}", headers={"Authorization": "Bearer signed-token"}
    )

    assert response.status_code == 403
    assert requests == []


async def test_admin_payment_forwards_request(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    payment_id = uuid4()
    response = await client.get(
        f"/api/admin/payments/{payment_id}", headers={"Authorization": "Bearer signed-token"}
    )

    assert response.status_code == 200
    assert requests[0].url.path == f"/admin/payments/{payment_id}"
    assert requests[0].headers["authorization"] == "Bearer signed-token"


async def test_create_order_requires_idempotency_key(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.post(
        "/api/orders",
        headers={"Authorization": "Bearer signed-token"},
        json={
            "receipt_email": "buyer@example.com",
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
        },
    )

    assert response.status_code == 422
    assert requests == []


async def test_create_order_forwards_idempotency_key_and_body(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    product_id = uuid4()
    response = await client.post(
        "/api/orders",
        headers={"Authorization": "Bearer signed-token", "Idempotency-Key": "checkout-1"},
        json={
            "receipt_email": "buyer@example.com",
            "items": [{"product_id": str(product_id), "quantity": 2}],
        },
    )

    assert response.status_code == 200
    assert requests[0].headers["idempotency-key"] == "checkout-1"
    assert requests[0].headers["authorization"] == "Bearer signed-token"
    assert requests[0].url.path == "/orders"
    assert b'"quantity":2' in requests[0].content


async def test_upstream_connection_error_becomes_503(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    from api_gateway.main import app
    from api_gateway.routers.dependencies import get_http_client

    client, _ = gateway
    broken_client = AsyncMock()
    broken_client.request.side_effect = httpx.ConnectError("upstream down")
    app.dependency_overrides[get_http_client] = lambda: broken_client

    response = await client.get("/api/products")

    assert response.status_code == 503
    assert response.json() == {"detail": "Upstream service unavailable"}
