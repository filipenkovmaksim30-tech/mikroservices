

from decimal import Decimal
from typing import Protocol
from uuid import UUID


class PaymentProvider(Protocol):
    async def charge(
        self,
        order_id: UUID,
        amount: Decimal,
        currency: str
    ):
        ...