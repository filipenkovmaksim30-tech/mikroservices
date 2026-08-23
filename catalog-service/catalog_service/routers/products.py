from typing import Annotated
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, status

from catalog_service.db.session import get_session
from catalog_service.schemas.products import ProductCreate, ProductRead
from catalog_service.services.products import ProductsService
from catalog_service.repositories.products import ProductRepository



router = APIRouter(prefix="/products", tags=["Products"])


SessionDependency = Annotated[AsyncSession, Depends(get_session)]

async def get_product_service(session: SessionDependency) -> ProductsService:
    return ProductsService(
        session=session,
        repository=ProductRepository(session=session),
    )

ServiceDependency = Annotated[ProductsService, Depends(get_product_service)]

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
