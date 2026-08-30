
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.products import Product
from catalog_service.repositories.products import ProductRepository
from catalog_service.exceptions import InsufficientStockError, ProductNotFoundError
from catalog_service.schemas.products import ProductCreate, ProductUpdate

class ProductsService:
    def __init__(
        self, 
        session: AsyncSession,
        repository: ProductRepository,
    ):
        self._session = session
        self._repository = repository

    async def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(
            id=uuid4(),
            **product_data.model_dump(),
        )
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

    async def update_product(self, product_id: UUID, product_data: ProductUpdate) -> Product:
        async with self._session.begin():
            product = await self._repository.get_by_id(product_id)
            if product is None:
                raise ProductNotFoundError(product_id=product_id)

            changes = product_data.model_dump(exclude_unset=True)

            for field_name, value in changes.items():
                setattr(product, field_name, value)

            await self._session.flush()

        return product

    async def deactivate_product(self, product_id: UUID) -> None:
        async with self._session.begin():
            product = await self._repository.get_by_id(product_id)
            if product is None:
                raise ProductNotFoundError(product_id=product_id)

            if not product.is_active:
                return

            product.is_active = False

    async def activate_product(self, product_id: UUID) -> Product:
        async with self._session.begin():
            product = await self._repository.get_by_id(product_id)

            if product is None:
                raise ProductNotFoundError(product_id=product_id)

            if product.is_active is True:
                return product

            product.is_active = True

        return product

    async def get_products(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[Product], int]:
        async with self._session.begin():
            products = await self._repository.get_list_products(
                limit=limit,
                offset=offset,
            )
            total = await self._repository.count_active()

        return products, total


