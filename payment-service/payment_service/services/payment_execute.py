
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.repositories.payments import PaymentRepository
from payment_service.repositories.outbox import RabbitMQOutboxRepository
from payment_service.services.payment_provider import PaymentProvider
from payment_service.messaging.contracts import PaymentFailedV1, PaymentSucceededV1
from payment_service.db.models.payments import Payment, PaymentStatus
from payment_service.db.models.payments_outbox import RabbitMQOutboxEvent

class PaymentExecuteService:
    def __init__(
        self,
        session: AsyncSession,
        outbox_repository: RabbitMQOutboxRepository,
        payment_repository: PaymentRepository,
        payment_provider: PaymentProvider,

    ) -> None:
        self._session = session
        self._outbox_repository = outbox_repository
        self._payment_repository = payment_repository
        self._payment_provider = payment_provider

    def _build_payment_succeeded_event(self, payment: Payment) -> RabbitMQOutboxEvent:
        if payment.status is not PaymentStatus.SUCCEEDED:
            raise ValueError(f"status must be succeeded, not {payment.status}")
        if payment.completed_at is None:
            raise ValueError("completed_at must be set for succeeded payment")
        payload_succeeded = PaymentSucceededV1(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            currency=payment.currency,
            completed_at=payment.completed_at,
        )

        payload = payload_succeeded.model_dump(mode="json")

        return RabbitMQOutboxEvent(
            aggregate_id=payment.id,
            correlation_id=payment.order_id,
            event_type="payment.succeeded",
            event_version=1,
            payload=payload,
        )
        

    def _build_payment_failed_event(self, payment: Payment) -> RabbitMQOutboxEvent:
        if payment.status is not PaymentStatus.FAILED:
            raise ValueError(f"status must be failed, not {payment.status}")
        if payment.failure_code is None:
            raise ValueError("failure_code must be non empty")
        if payment.completed_at is None:
            raise ValueError("completed_at must be non empty")
        payload_failed = PaymentFailedV1(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            currency=payment.currency,
            failure_code=payment.failure_code,
            completed_at=payment.completed_at,
        )

        payload = payload_failed.model_dump(mode="json")
        
        return RabbitMQOutboxEvent(
            aggregate_id=payment.id,
            correlation_id=payment.order_id,
            event_type="payment.failed",
            event_version=1,
            payload=payload,
        )

    async def execute(self, payment_id: UUID) -> bool:
        async with self._session.begin():
            payment = await self._payment_repository.get_by_id(payment_id)
            if payment is None:
                raise ValueError("payment not found")
            if payment.status is not PaymentStatus.PENDING:
                return False
            order_id = payment.order_id
            amount = payment.amount
            currency = payment.currency

        payment_result = await self._payment_provider.charge(
            order_id=order_id,
            amount=amount,
            currency=currency,
        )

        async with self._session.begin():
            payment = await self._payment_repository.get_by_id(payment_id)
            if payment is None:
                raise ValueError("payment not found")

            await self._session.refresh(payment)

            if payment.status is not PaymentStatus.PENDING:
                return False

            completed_at = datetime.now(UTC)

            if payment_result.succeeded:
                await self._payment_repository.mark_succeeded(
                    payment=payment,
                    completed_at=completed_at,
                )
                succeeded_event = self._build_payment_succeeded_event(payment)
                await self._outbox_repository.add(succeeded_event)

            else:
                if not payment_result.failure_code:
                    raise RuntimeError("Failed payment result must contain failure_code")

                await self._payment_repository.mark_failed(
                    payment=payment,
                    failure_code=payment_result.failure_code,
                    completed_at=completed_at,
                )
                failed_event = self._build_payment_failed_event(payment)
                await self._outbox_repository.add(failed_event)
            
        return True
