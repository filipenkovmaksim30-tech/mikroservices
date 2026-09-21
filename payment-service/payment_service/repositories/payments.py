
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
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
        payment.processing_token = None
        payment.processing_expires_at = None
        await self._session.flush()
        return payment

    async def mark_failed(self, payment: Payment, failure_code: str, completed_at: datetime) -> Payment:
        payment.status = PaymentStatus.FAILED
        payment.failure_code = failure_code
        payment.completed_at = completed_at
        payment.processing_token = None
        payment.processing_expires_at = None
        await self._session.flush()
        return payment

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        statement = select(Payment).where(Payment.id == payment_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, payment_id: UUID) -> Payment | None:
        statement = select(Payment).where(Payment.id == payment_id).with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: UUID) -> Payment | None:
        statement = select(Payment).where(Payment.order_id == order_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_runnable_ids(self, limit: int) -> list[UUID]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        statement = (
            select(Payment.id)
            .where(
                or_(
                    Payment.status == PaymentStatus.PENDING,
                    and_(
                        Payment.status == PaymentStatus.PROCESSING,
                        Payment.processing_expires_at <= func.now(),
                    ),
                )
            )
            .order_by(Payment.created_at, Payment.id)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def claim_for_processing(
        self,
        payment_id: UUID,
        processing_token: UUID,
        processing_expires_at: datetime,
    ) -> Payment | None:
        statement = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                or_(
                    Payment.status == PaymentStatus.PENDING,
                    and_(
                        Payment.status == PaymentStatus.PROCESSING,
                        Payment.processing_expires_at <= func.now(),
                    ),
                ),
            )
            .values(
                status=PaymentStatus.PROCESSING,
                processing_token=processing_token,
                processing_expires_at=processing_expires_at,
                processing_attempts=Payment.processing_attempts + 1,
            )
            .returning(Payment)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()


