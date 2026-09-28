import logging
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY

from api_gateway.observability import install_http_logging

pytestmark = pytest.mark.asyncio


async def test_request_id_is_returned_and_forwarded(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, upstream_requests = gateway

    response = await client.get(
        "/api/products",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-123"
    assert upstream_requests[0].headers["x-request-id"] == "test-request-123"


async def test_http_metrics_use_route_template_and_ignore_scrapes(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, _ = gateway
    labels = {"method": "GET", "route": "/products/{product_id}", "status_code": "200"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0

    http_logger = logging.getLogger("api_gateway.observability.http")
    with patch.object(http_logger, "log") as access_log:
        response = await client.get("/api/products/35667d8a-cc21-447a-941d-ec19d2a48956")
        metrics = await client.get("/metrics/")

    assert response.status_code == 200
    assert metrics.status_code == 200
    assert access_log.call_count == 1
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1
    assert REGISTRY.get_sample_value("http_request_duration_seconds_count", labels) is not None
    assert "http_requests_total" in metrics.text
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1


async def test_unmatched_path_uses_bounded_route_label(
    gateway: tuple[httpx.AsyncClient, list[httpx.Request]],
) -> None:
    client, _ = gateway
    labels = {"method": "GET", "route": "unmatched", "status_code": "404"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0

    response = await client.get("/not-a-route/123")

    assert response.status_code == 404
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1


async def test_failed_metrics_request_is_logged() -> None:
    app = FastAPI()
    install_http_logging(app)

    @app.get("/metrics/")
    async def unavailable_metrics() -> PlainTextResponse:
        return PlainTextResponse("unavailable", status_code=503)

    http_logger = logging.getLogger("api_gateway.observability.http")
    with patch.object(http_logger, "log") as access_log:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/metrics/")

    assert response.status_code == 503
    access_log.assert_called_once()
    assert access_log.call_args.args[1] == "http.request.completed"
