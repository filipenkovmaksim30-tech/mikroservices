from uuid import UUID

from fastapi import APIRouter, Depends, status

from catalog_service.schemas.products import ProductCreate, ProductRead, ProductUpdate
from catalog_service.routers.dependencies import ServiceDependency, require_admin


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