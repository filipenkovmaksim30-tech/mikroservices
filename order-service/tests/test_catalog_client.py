from uuid import uuid4

import httpx
import pytest

from messaging_lab.exceptions import CatalogUnavailableError, InvalidCatalogResponseError
from messaging_lab.integrations.catalog import CatalogClient


async def test_catalog_client_validates_batch_response() -> None:
    product_id = uuid4()

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/products/batch"
        assert str(product_id) in request.content.decode()
        return httpx.Response(200, json={
            "products": [{
                "id": str(product_id), "price": "100.00",
                "stock_quantity": 5, "is_active": True,
            }]
        })

    async with httpx.AsyncClient(
        base_url="http://catalog.test", transport=httpx.MockTransport(upstream)
    ) as client:
        products = await CatalogClient(client).get_products_by_ids({product_id})

    assert len(products) == 1
    assert products[0].id == product_id


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(503), CatalogUnavailableError),
        (httpx.Response(404), InvalidCatalogResponseError),
        (httpx.Response(200, text="not JSON"), InvalidCatalogResponseError),
        (httpx.Response(200, json={"products": "wrong"}), InvalidCatalogResponseError),
    ],
)
async def test_catalog_client_classifies_upstream_errors(
    response: httpx.Response, expected: type[Exception]
) -> None:
    async with httpx.AsyncClient(
        base_url="http://catalog.test",
        transport=httpx.MockTransport(lambda _request: response),
    ) as client:
        with pytest.raises(expected):
            await CatalogClient(client).get_products_by_ids({uuid4()})


async def test_catalog_client_connection_error_is_unavailable() -> None:
    def disconnect(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(
        base_url="http://catalog.test", transport=httpx.MockTransport(disconnect)
    ) as client:
        with pytest.raises(CatalogUnavailableError):
            await CatalogClient(client).get_products_by_ids({uuid4()})
