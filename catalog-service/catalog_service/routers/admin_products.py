from fastapi import APIRouter, Depends, status

from catalog_service.schemas.products import ProductCreate, ProductRead
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