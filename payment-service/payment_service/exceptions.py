


from decimal import Decimal
from uuid import UUID


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

