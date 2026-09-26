from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.db.models.payments import Payment, PaymentStatus
from payment_service.exceptions import OrderNotFoundError, PaymentNotFoundError
from payment_service.repositories.payments import PaymentRepository


class PaymentService:
    def __init__(
        self,
        session: AsyncSession,
        payment_repository: PaymentRepository,
    ) -> None:
        self._session = session
        self._payment_repository = payment_repository

    async def get_by_id(self, payment_id: UUID) -> Payment:
        async with self._session.begin():
            payment = await self._payment_repository.get_by_id(payment_id)
            if payment is None:
                raise PaymentNotFoundError(payment_id) 
        return payment


    async def get_payments(
        self, status: PaymentStatus | None, limit: int, offset: int
    ) -> list[Payment]:
        async with self._session.begin():
            payments = await self._payment_repository.get_payments(limit, offset, status)
        return payments

    async def get_by_order_id(self, order_id: UUID) -> Payment:
        async with self._session.begin():
            payment = await self._payment_repository.get_by_order_id(order_id)

            if payment is None:
                raise OrderNotFoundError(order_id)
        return payment
