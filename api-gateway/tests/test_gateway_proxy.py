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


@pytest.mark.parametrize(
    ("path", "upstream_path"),
    [
        ("/api/products/{id}", "/products/{id}"),
        ("/api/admin/orders/{id}", "/admin/orders/{id}"),
        ("/api/admin/payments/by-order/{id}", "/admin/payments/by-order/{id}"),
    ],
)
async def test_id_routes_forward_exact_resource(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
    path: str,
    upstream_path: str,
) -> None:
    client, requests = gateway
    resource_id = str(uuid4())
    response = await client.get(
        path.format(id=resource_id), headers={"Authorization": "Bearer signed-token"}
    )

    assert response.status_code == 200
    assert requests[0].url.path == upstream_path.format(id=resource_id)


async def test_admin_payments_forwards_status_filter(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.get(
        "/api/admin/payments",
        params={"status": "succeeded", "limit": 3, "offset": 2},
        headers={"Authorization": "Bearer signed-token"},
    )

    assert response.status_code == 200
    assert dict(requests[0].url.params) == {
        "status": "succeeded", "limit": "3", "offset": "2"
    }


async def test_analytics_summary_forwards_date_range(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.get(
        "/api/admin/analytics/summary",
        params={"date_from": "2026-01-01T00:00:00Z", "date_to": "2026-02-01T00:00:00Z"},
        headers={"Authorization": "Bearer signed-token"},
    )

    assert response.status_code == 200
    assert requests[0].url.host == "analytics.test"
    assert requests[0].url.path == "/analytics/summary"
    assert requests[0].url.params["date_from"].startswith("2026-01-01T00:00:00")


async def test_register_forwards_validated_json(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "buyer@example.com",
            "password": "password12345",
            "repeat_password": "password12345",
        },
    )

    assert response.status_code == 200
    assert requests[0].url.path == "/auth/register"
    assert b'"email":"buyer@example.com"' in requests[0].content


async def test_logout_forwards_cookie(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, requests = gateway
    client.cookies.set("refresh_token", "original", domain="gateway.test", path="/api/auth")
    response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    assert requests[0].headers["cookie"] == "refresh_token=original"

async def test_upstream_429_forwards_retry_after(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    from api_gateway.main import app
    from api_gateway.routers.dependencies import get_http_client

    client, _ = gateway
    upstream = AsyncMock()
    upstream.request.return_value = httpx.Response(
        429,
        json={"detail": "Too many requests"},
        headers={"Retry-After": "60"},
    )
    app.dependency_overrides[get_http_client] = lambda: upstream

    response = await client.get("/api/products")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {"detail": "Too many requests"}
    upstream.request.assert_awaited_once()