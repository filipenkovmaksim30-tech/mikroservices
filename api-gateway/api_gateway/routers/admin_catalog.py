

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    require_admin,
)
from api_gateway.schemas.catalog import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(
    tags=["Admin Catalog"], 
    prefix="/admin/products", 
    dependencies=[Depends(require_admin)]
)

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductRead,
    summary="Создать товар",
)
async def create_product(
    authorization_headers: AuthorizationHeadersDependency,
    payload: ProductCreate,
    client: HttpClientDependency,
    settings: SettingsDependency
) -> Response:
    url = f"{settings.catalog_base_url.rstrip("/")}/admin/products"

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        json_body=payload.model_dump(mode="json"),
        headers=authorization_headers,
    )

    return build_gateway_response(upstream_response)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить товар по ID"
)

async def edit_product(
    authorization_headers: AuthorizationHeadersDependency,
    product_id: UUID,
    product_data: ProductUpdate,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
    url = f"{settings.catalog_base_url.rstrip("/")}/admin/products/{product_id}"

    upstream_response = await request_upstream(
        client=client,
        method="PATCH",
        url=url,
        json_body=product_data.model_dump(mode="json", exclude_unset=True),
        headers=authorization_headers,
    )
        
    return build_gateway_response(upstream_response)

@router.post(
    "/{product_id}/activate",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="Активировать товар по ID"
)

async def activate_product(
    authorization_headers: AuthorizationHeadersDependency,
    product_id: UUID,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
        
    url = (
        f"{settings.catalog_base_url.rstrip("/")}"
        f"/admin/products/{product_id}/activate"
    )

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        headers=authorization_headers,
    )
    
    return build_gateway_response(upstream_response)
    

@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Деактивировать товар по ID"
)
async def deactivate_product(
    authorization_headers: AuthorizationHeadersDependency,
    product_id: UUID,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
    
    url = f"{settings.catalog_base_url.rstrip("/")}/admin/products/{product_id}"

    upstream_response = await request_upstream(
        client=client,
        method="DELETE",
        url=url,
        headers=authorization_headers,
    )

    return build_gateway_response(upstream_response)
