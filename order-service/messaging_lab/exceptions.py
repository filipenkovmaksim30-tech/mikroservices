from decimal import Decimal
from uuid import UUID


class OrderValidationError(Exception):
    """Base error for an order request that is structurally valid but cannot be fulfilled."""


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Заказ с id={order_id} не найден")


class InvalidOrderAmountError(OrderValidationError):
    def __init__(self, total_amount: Decimal) -> None:
        self.total_amount = total_amount
        super().__init__(f"Order total_amount must be non-negative, got {total_amount}")


class EmptyOrderError(OrderValidationError):
    def __init__(self) -> None:
        super().__init__("Order must contain at least one item")


class ProductsNotFoundError(OrderValidationError):
    def __init__(self, product_ids: set[UUID]) -> None:
        self.product_ids = product_ids
        super().__init__(f"Products were not found: {sorted(map(str, product_ids))}")


class DuplicateProductsError(OrderValidationError):
    def __init__(self, product_ids: set[UUID]) -> None:
        self.product_ids = product_ids
        super().__init__(f"Products are duplicated: {sorted(map(str, product_ids))}")


class InactiveProductsError(OrderValidationError):
    def __init__(self, product_ids: set[UUID]) -> None:
        self.product_ids = product_ids
        super().__init__(f"Products are inactive: {sorted(map(str, product_ids))}")

class PermanentPaymentResultError(Exception):
    """Base error for a payment result that cannot succeed after retry."""


class PaymentAmountMismatchError(PermanentPaymentResultError):
    def __init__(
        self,
        order_id: UUID,
        expected_amount: Decimal,
        actual_amount: Decimal,
    ) -> None:
        self.order_id = order_id
        self.expected_amount = expected_amount
        self.actual_amount = actual_amount
        super().__init__(
            f"Payment amount mismatch for order_id={order_id}: "
            f"expected={expected_amount}, actual={actual_amount}"
        )


class InvalidOrderPaymentStatusError(PermanentPaymentResultError):
    def __init__(
        self,
        order_id: UUID,
        current_order_status: str,
        target_order_status: str,
    ) -> None:
        self.order_id = order_id
        self.current_order_status = current_order_status
        self.target_order_status = target_order_status
        super().__init__(
            f"Cannot change order payment status for order_id={order_id}: "
            f"current_status={current_order_status}, "
            f"target_status={target_order_status}"
        )
