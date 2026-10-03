from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from catalog_service.media.glb_validation import MAX_GLB_BYTES, InvalidProductModelError
from catalog_service.media.image_processing import (
    MAX_FILE_BYTES,
    InvalidProductImageError,
)
from catalog_service.routers.dependencies import (
    MediaServiceDependency,
    ServiceDependency,
    require_admin,
)
from catalog_service.schemas.products import (
    ProductCreate,
    ProductImageOrderUpdate,
    ProductImageRead,
    ProductModelRead,
    ProductRead,
    ProductUpdate,
)

router = APIRouter(
    prefix="/admin/products", 
    tags=["Admin Products"], 
    dependencies=[Depends(require_admin)]
)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар",
)
async def create_product(
    product_data: ProductCreate,
    service: ServiceDependency,
):  
    return await service.create_product(product_data=product_data)

@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="Изменить товар по ID"
)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    service: ServiceDependency,
):
    return await service.update_product(product_id=product_id, product_data=product_data)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Деактивировать товар"
)
async def delete_product(
    product_id: UUID,
    service: ServiceDependency,
):
    await service.deactivate_product(product_id=product_id)

@router.post(
    "/{product_id}/activate",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="Активировать товар"
)
async def activate_product(
    product_id: UUID,
    service: ServiceDependency,
):
    return await service.activate_product(product_id=product_id)


@router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить изображение к товару"
)
async def upload_file(
    service: MediaServiceDependency,
    product_id: UUID,
    file: Annotated[UploadFile, File()],
):
    try:
        file_bytes = await file.read(MAX_FILE_BYTES + 1)
    finally:
        await file.close()

    if len(file_bytes) > MAX_FILE_BYTES:
        raise InvalidProductImageError("Image must not exceed 5 MB")

    image = await service.add_image(product_id, file_bytes)
    return {"id": image.id, "position": image.position}


@router.put(
    "/{product_id}/images/order",
    response_model=list[ProductImageRead],
    status_code=status.HTTP_200_OK,
    summary="Изменить порядок изображений товара",
)
async def reorder_images(
    product_id: UUID,
    payload: ProductImageOrderUpdate,
    service: MediaServiceDependency,
) -> list[ProductImageRead]:
    images = await service.reorder_images(product_id, payload.image_ids)
    return [ProductImageRead.model_validate(image) for image in images]

@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить изображение у товара",
)
async def delete_image(
    service: MediaServiceDependency,
    product_id: UUID,
    image_id: UUID,
) -> None:
    await service.delete_image(product_id, image_id)


@router.put(
    "/{product_id}/model-3d",
    response_model=ProductModelRead,
    summary="Загрузить или заменить 3D-модель товара",
)
async def replace_model(
    product_id: UUID,
    service: MediaServiceDependency,
    file: Annotated[UploadFile, File()],
) -> ProductModelRead:
    try:
        file_bytes = await file.read(MAX_GLB_BYTES + 1)
    finally:
        await file.close()
    if len(file_bytes) > MAX_GLB_BYTES:
        raise InvalidProductModelError("GLB must not exceed 25 MiB")
    key = await service.replace_model(product_id, file_bytes)
    return ProductModelRead(model_3d_url=f"/media/{key}")


@router.delete(
    "/{product_id}/model-3d",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить 3D-модель товара",
)
async def delete_model(
    product_id: UUID,
    service: MediaServiceDependency,
) -> None:
    await service.delete_model(product_id)
