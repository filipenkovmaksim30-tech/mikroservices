from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from analytics_service.schemas.analytics import AnalyticsSummaryResponse


def isolated_app(monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, object, object, object]:
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "unused-test-key.pem")
    router_module = import_module("analytics_service.routers.analytics_order")
    dependencies = import_module("analytics_service.routers.dependencies")
    api_module = import_module("analytics_service.api")
    exceptions = import_module("analytics_service.exceptions")
    app = FastAPI()
    app.include_router(router_module.router)
    app.add_exception_handler(
        exceptions.PermissionDeniedError, api_module.handle_permission_denied
    )
    return (
        app,
        dependencies.get_analytics_service,
        dependencies.require_admin,
        dependencies.get_current_principal,
    )


async def test_admin_summary_proxies_valid_period_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, get_service, require_admin, _ = isolated_app(monkeypatch)
    summary = AnalyticsSummaryResponse(
        orders_count=2,
        paid_orders_count=1,
        payment_failed_count=0,
        revenue="100.00",
        average_order_value="100.00",
        items_quantity=2,
    )
    service = SimpleNamespace(get_summary=AsyncMock(return_value=summary))
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[require_admin] = lambda: None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/analytics/summary",
            params={"date_from": "2026-01-01T00:00:00Z", "date_to": "2026-02-01T00:00:00Z"},
        )

    assert response.status_code == 200
    assert response.json()["revenue"] == "100.00"
    service.get_summary.assert_awaited_once()


async def test_non_admin_cannot_read_analytics(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _, _, get_principal = isolated_app(monkeypatch)
    app.dependency_overrides[get_principal] = lambda: SimpleNamespace(role="customer")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/analytics/summary",
            params={"date_from": "2026-01-01T00:00:00Z", "date_to": "2026-02-01T00:00:00Z"},
        )

    assert response.status_code == 403
