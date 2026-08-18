

from uuid import UUID

class ProductValidationError(Exception):
    """Base error for an product request that is structurally valid but cannot be fulfilled."""

class InsufficientStockError(Exception):
    def __init__(self, product_id: UUID, quantity: int, stock_quantity: int):
        super().__init__(f"Products with id={product_id} requsted_quantity={quantity}, stock_quantity={stock_quantity}")


class ProductNotFoundError(Exception):
    def __init__(self, product_id: UUID):
        super().__init__(f"Product with id={product_id} not found")

class ProductsNotFoundError(Exception):
    def __init__(self, missing_ids: set[UUID]):
        super().__init__(f"Products with ids={missing_ids} not found")
