from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import HttpClientDependency, SettingsDependency

LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]

router = APIRouter(tags=["Catalog"], prefix="/products")

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Получить товары"
)
async def get_products(
    client: HttpClientDependency,
    settings: SettingsDependency,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
) -> Response:  
    url = f"{settings.catalog_base_url.rstrip('/')}/products"
    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params={
            "offset": offset,
            "limit": limit
        }
    )

    return build_gateway_response(upstream_response)

@router.get(
    "/{product_id}",
    summary="Получить товар по ID"
)
async def get_product_by_id(
    product_id: UUID,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url= (
        f"{settings.catalog_base_url.rstrip("/")}"
        f"/products/{product_id}"
    )

    upstream_response = await request_upstream(
        client=client,
        url=url,
        method="GET"
    )
    return build_gateway_response(upstream_response)
