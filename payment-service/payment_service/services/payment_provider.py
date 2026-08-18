

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentResult:
    succeeded: bool
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if self.succeeded and self.failure_code is not None:
            raise ValueError(
                "Successful payment must not contain failure_code"
            )

        if not self.succeeded and (
            self.failure_code is None
            or not self.failure_code.strip()
        ):
            raise ValueError(
                "Failed payment must contain non-empty failure_code"
            )


class PaymentProvider(Protocol):
    async def charge(
        self,
        order_id: UUID,
        amount: Decimal,
        currency: str
    ) -> PaymentResult:
        ...

