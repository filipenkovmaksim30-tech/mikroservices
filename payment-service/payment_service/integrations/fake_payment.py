import asyncio
from decimal import Decimal
from uuid import UUID

from payment_service.services.payment_provider import PaymentResult

class FakePaymentProvider:
    def __init__(
        self, 
        should_succeed: bool,
        delay_seconds: float = 5.00,
        failure_code: str = "payment_declined"
        ) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")
        
        if not failure_code or not failure_code.strip():
            raise ValueError("failure_code must be non-empty")
            
        self._should_succeed = should_succeed
        self._delay_seconds = delay_seconds
        self._failure_code = failure_code

    async def charge(
        self,
        order_id: UUID,
        amount: Decimal,
        currency: str
    ) -> PaymentResult:
        await asyncio.sleep(self._delay_seconds)

        if self._should_succeed:
            return PaymentResult(succeeded=True)

        return PaymentResult(
            succeeded=False,
            failure_code=self._failure_code,
        )
