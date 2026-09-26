


from decimal import Decimal
from uuid import UUID

class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: UUID):
        super().__init__(f"Payment with payment_id={payment_id} not found")

class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID):
        super().__init__(f"Payment with order_id={order_id} not found")


class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Administrator privileges required")
        

class PaymentRequestConflictError(Exception):
    def __init__(
        self,
        order_id: UUID,
        existing_amount: Decimal,
        requested_amount: Decimal,
        existing_currency: str,
        requested_currency: str, 
        ):
        self.order_id = order_id
        self.existing_amount = existing_amount
        self.requested_amount = requested_amount
        self.existing_currency = existing_currency
        self.requested_currency = requested_currency

        super().__init__(
            f"Payment request conflicts with existing payment "
            f"for order_id={order_id}: "
            f"existing_amount={existing_amount}, "
            f"requested_amount={requested_amount}, "
            f"existing_currency={existing_currency}, "
            f"requested_currency={requested_currency}"
        )

