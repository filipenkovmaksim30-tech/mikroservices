from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    require_admin,
)
from api_gateway.schemas.catalog import (
    ProductCreate,
    ProductImageOrderUpdate,
    ProductImageRead,
    ProductRead,
    ProductUpdate,
)

MAX_FILE_BYTES = 5 * 1024 * 1024

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

@router.post(
    "/{product_id}/images",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductImageRead,
    summary="Добавить изображение товару"
)
async def add_image(
    authorization_headers: AuthorizationHeadersDependency,
    settings: SettingsDependency,
    client: HttpClientDependency,
    product_id: UUID,
    file: Annotated[UploadFile, File()],
):
    try:
        file_bytes = await file.read(MAX_FILE_BYTES + 1)
    finally:
        await file.close()

    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image must not exceed 5 MB",
        )

    url = (
        f"{settings.catalog_base_url.rstrip("/")}"
        f"/admin/products/{product_id}/images"
    )

    files={
        "file": (
            file.filename or "upload",
            file_bytes,
            file.content_type or "application/octet-stream",
        )
    }

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        files=files,
        headers=authorization_headers,
    )

    return build_gateway_response(upstream_response)

@router.put(
    "/{product_id}/images/order",
    status_code=status.HTTP_200_OK,
    response_model=list[ProductImageRead],
    summary="Изменить порядок изображений товара",
)
async def reorder_images(
    authorization_headers: AuthorizationHeadersDependency,
    settings: SettingsDependency,
    client: HttpClientDependency,
    product_id: UUID,
    payload: ProductImageOrderUpdate,
) -> Response:
    url = f"{settings.catalog_base_url.rstrip('/')}/admin/products/{product_id}/images/order"
    upstream_response = await request_upstream(
        client=client,
        method="PUT",
        url=url,
        json_body=payload.model_dump(mode="json"),
        headers=authorization_headers,
    )
    return build_gateway_response(upstream_response)
@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить изображение у товара"
)
async def delete_image(
    authorization_headers: AuthorizationHeadersDependency,
    settings: SettingsDependency,
    client: HttpClientDependency,
    product_id: UUID,
    image_id: UUID,
):
    url = (
        f"{settings.catalog_base_url.rstrip("/")}"
        f"/admin/products/{product_id}/images/{image_id}"
    )

    upstream_response = await request_upstream(
        client=client,
        method="DELETE",
        url=url,
        headers=authorization_headers,
    )

    return build_gateway_response(upstream_response)
