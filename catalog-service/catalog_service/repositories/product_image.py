
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.product_image import ProductImage

class ProductImageRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(self, image: ProductImage) -> ProductImage:
       self._session.add(image)
       await self._session.flush()
       return image


    async def get_by_id(self, image_id: UUID, product_id: UUID) -> ProductImage | None:
        statement = (
            select(ProductImage)
            .where(ProductImage.id == image_id, ProductImage.product_id == product_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_by_product_id(self, product_id: UUID) -> list[ProductImage]:
        statement = (
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.position)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
    
    async def delete(self, image: ProductImage) -> None:
        await self._session.delete(image)
        await self._session.flush()