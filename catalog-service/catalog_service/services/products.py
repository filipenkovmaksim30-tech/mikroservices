
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.products import Product
from catalog_service.repositories.products import ProductRepository
from catalog_service.exceptions import ProductNotFoundError, InsufficientStockError, ProductsNotFoundError

class ProductsService:
    def __init__(
        self, 
        session: AsyncSession,
        repository: ProductRepository,
    ):
        self._session = session
        self._repository = repository

    async def create_product(self, product: Product) -> Product:
        async with self._session.begin():
            new_product = await self._repository.add(product)
        return new_product

    async def get_product_by_id(self, product_id: UUID) -> Product:
        async with self._session.begin():
            product = await self._repository.get_by_id(product_id)
            if product is None:
                raise ProductNotFoundError(product_id=product_id)
        return product

    async def get_products_by_ids(self, product_ids: set[UUID]) -> list[Product]:
        async with self._session.begin():
            products = await self._repository.get_by_ids(product_ids)
            found_ids = {product.id for product in products}
            missing_ids = product_ids - found_ids
            if missing_ids:
                raise ProductsNotFoundError(missing_ids)
        return products

    async def decrease_product_stock(self, product_id: UUID, quantity: int) -> int:
        async with self._session.begin():
            product = await self._repository.get_by_id(product_id)
            if product is None:
                raise ProductNotFoundError(product_id=product_id)
            product_quantity = await self._repository.set_stock_quantity(product_id=product_id, quantity=quantity)
            if product_quantity is None:
                raise InsufficientStockError(product_id=product_id, quantity=quantity, stock_quantity=product.stock_quantity)        
        return product_quantity


