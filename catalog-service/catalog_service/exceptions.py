from uuid import UUID


class ProductValidationError(Exception):
    """Base error for an product request that is structurally valid but cannot be fulfilled."""


class InsufficientStockError(Exception):
    def __init__(self, product_id: UUID, quantity: int, stock_quantity: int):
        super().__init__(
            f"Products with id={product_id} requsted_quantity={quantity}, "
            f"stock_quantity={stock_quantity}"
        )


class PermanentStockReservationFinalizationError(Exception):
    """Reservation finalization cannot be applied by retrying the same command."""


class InvalidReservationStatusError(PermanentStockReservationFinalizationError):
    def __init__(
        self,
        order_id: UUID,
        current_status: str,
        target_status: str,
    ) -> None:
        self.order_id = order_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot change reservation status for order_id={order_id}: "
            f"{current_status} -> {target_status}"
        )


class ReservationProductsMissingError(PermanentStockReservationFinalizationError):
    def __init__(self, order_id: UUID, product_ids: set[UUID]) -> None:
        self.order_id = order_id
        self.product_ids = product_ids
        missing_ids = ", ".join(sorted(str(product_id) for product_id in product_ids))
        super().__init__(f"Reservation products missing for order_id={order_id}: {missing_ids}")


class ProductNotFoundError(Exception):
    def __init__(self, product_id: UUID):
        super().__init__(f"Product with id={product_id} not found")


class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Administrator privileges required")


class ReservationNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Reservation with order_id={order_id} not found")
