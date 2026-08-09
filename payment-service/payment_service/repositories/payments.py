
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.db.models.payments import Payment, PaymentStatus

class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> Payment:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def mark_succeeded(self, payment: Payment, completed_at: datetime) -> Payment:
        payment.status = PaymentStatus.SUCCEEDED
        payment.completed_at = completed_at
        await self._session.flush()
        return payment

    async def mark_failed(self, payment: Payment, failure_code: str, completed_at: datetime) -> Payment:
        payment.status = PaymentStatus.FAILED
        payment.failure_code = failure_code
        payment.completed_at = completed_at
        await self._session.flush()
        return payment

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        statement = select(Payment).where(Payment.id == payment_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: UUID) -> Payment | None:
        statement = select(Payment).where(Payment.order_id == order_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
