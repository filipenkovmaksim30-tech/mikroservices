import logging
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from prometheus_client import REGISTRY, make_asgi_app

from auth_service.observability import install_http_logging


@pytest.mark.asyncio
async def test_http_metrics_record_route_and_status_without_counting_scrapes() -> None:
    app = FastAPI()
    app.mount("/metrics", make_asgi_app())
    install_http_logging(app)

    @app.get("/things/{item_id}")
    async def read_thing(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    labels = {"method": "GET", "route": "/things/{item_id}", "status_code": "200"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0

    http_logger = logging.getLogger("auth_service.observability.http")
    with patch.object(http_logger, "log") as access_log:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/things/123")
            metrics = await client.get("/metrics/")

    assert response.status_code == 200
    assert metrics.status_code == 200
    assert access_log.call_count == 1
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 1
    assert REGISTRY.get_sample_value("http_request_duration_seconds_count", labels) is not None
    assert REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "/metrics", "status_code": "200"},
    ) is None
