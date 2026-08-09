from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ids(self, product_ids: set[UUID]) -> list[Product]:
        if not product_ids:
            return []
        statement = select(Product).where(Product.id.in_(product_ids))
        result = await self._session.execute(statement)
        return list(result.scalars().all())
