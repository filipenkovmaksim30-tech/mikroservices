from uuid import UUID

from fastapi import APIRouter, status

from catalog_service.schemas.products import ProductRead
from catalog_service.routers.dependencies import ServiceDependency


router = APIRouter(
    prefix="/products", 
    tags=["Products"], 
)

@router.get(
    "/{product_id}",
    response_model=ProductRead,
    status_code=status.HTTP_200_OK,
    summary="Получить товар по ID",
)
async def get_by_id(
    product_id: UUID,
    service: ServiceDependency
):
    return await service.get_product_by_id(product_id=product_id)
