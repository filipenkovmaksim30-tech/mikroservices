from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.products import Product

class ProductRepository:
    def __init__(
        self,
        session: AsyncSession,
        ) -> None:
        self._session = session

    async def add(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        return product

    async def get_by_id(self, product_id: UUID) -> Product | None:
        statement = (
            select(Product).where(Product.id == product_id)
        )
        result = await self._session.execute(statement)
        product = result.scalar_one_or_none()
        return product

    async def set_stock_quantity(self, product_id: UUID, quantity: int):
        statement = (
            update(Product)
            .where(
                Product.id == product_id,
                Product.stock_quantity >= quantity,
            )
            .values(stock_quantity = Product.stock_quantity - quantity)
            .returning(Product.stock_quantity)
        )
        result = await self._session.execute(statement)
        new_quantity = result.scalar_one_or_none()
        return new_quantity

    async def get_by_ids(self, product_ids: set[UUID]) -> list[Product]:
        if not product_ids:
            return []
        statement = select(Product).where(Product.id.in_(product_ids))
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_list_products(self, limit: int, offset: int) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.created_at.desc(), Product.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        statement = select(func.count(Product.id)).where(Product.is_active.is_(True))
        result = await self._session.execute(statement)
        return result.scalar_one()
