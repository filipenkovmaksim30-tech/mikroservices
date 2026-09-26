from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest_asyncio

from api_gateway.main import app
from api_gateway.routers.dependencies import (
    get_http_client,
    get_settings,
    get_token_verifier,
)


@pytest_asyncio.fixture
async def gateway() -> AsyncIterator[tuple[httpx.AsyncClient, list[httpx.Request]]]:
    requests: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/auth/token":
            return httpx.Response(
                200,
                json={"access_token": "test-access", "token_type": "bearer"},
                headers={"set-cookie": "refresh_token=secret; HttpOnly; Path=/api/auth"},
            )
        if request.url.path == "/auth/refresh":
            return httpx.Response(
                200,
                json={"access_token": "rotated-access", "token_type": "bearer"},
                headers={"set-cookie": "refresh_token=rotated; HttpOnly; Path=/api/auth"},
            )
        return httpx.Response(200, json={"ok": True})

    settings = SimpleNamespace(
        catalog_base_url="http://catalog.test",
        auth_base_url="http://auth.test",
        orders_base_url="http://orders.test",
        analytics_base_url="http://analytics.test",
        payment_base_url="http://payment.test",
        refresh_cookie_name="refresh_token",
    )
    verifier = Mock()
    verifier.decode_access_token.return_value = SimpleNamespace(role="admin")

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as upstream_client:
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_http_client] = lambda: upstream_client
        app.dependency_overrides[get_token_verifier] = lambda: verifier
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://gateway.test"
            ) as client:
                yield client, requests
        finally:
            app.dependency_overrides.clear()
