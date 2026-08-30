import httpx
from uuid import UUID

from pydantic import ValidationError

from messaging_lab.schemas.catalog import (
    CatalogProductSnapshot,
    CatalogBatchRequest,
    CatalogBatchResponse
)

from messaging_lab.exceptions import (
    InvalidCatalogResponseError,
    CatalogUnavailableError,
)


class CatalogClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http_client = http_client

    async def get_products_by_ids(self, product_ids: set[UUID]) -> list[CatalogProductSnapshot]:

        request_data = CatalogBatchRequest(product_ids=product_ids)
        try:

            response = await self._http_client.post(
                "/products/batch",
                json=request_data.model_dump(mode="json"),
            )
        except httpx.RequestError as exc:
            raise CatalogUnavailableError() from exc

        if response.status_code >= 500:
            raise CatalogUnavailableError()

        if not response.is_success:
            raise InvalidCatalogResponseError()

        try:

            response_data = CatalogBatchResponse.model_validate(response.json())

        except (ValueError, ValidationError) as exc:
            raise InvalidCatalogResponseError() from exc

        return response_data.products