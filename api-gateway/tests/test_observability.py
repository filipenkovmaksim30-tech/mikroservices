import httpx
import pytest

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
