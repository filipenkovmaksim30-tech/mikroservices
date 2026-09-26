
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.repositories.payments import PaymentRepository
from payment_service.repositories.outbox import RabbitMQOutboxRepository
from payment_service.services.payment_provider import PaymentProvider
from payment_service.messaging.contracts import PaymentFailedV1, PaymentSucceededV1
from payment_service.db.models.payments import Payment, PaymentStatus
from payment_service.db.models.payments_outbox import RabbitMQOutboxEvent

logger = logging.getLogger(__name__)

class PaymentExecuteService:
    def __init__(
        self,
        session: AsyncSession,
        outbox_repository: RabbitMQOutboxRepository,
        payment_repository: PaymentRepository,
        payment_provider: PaymentProvider,
        payment_processing_lease_seconds: int,

    ) -> None:

        if payment_processing_lease_seconds <= 0:
            raise ValueError("payment_processing_lease_seconds must be positive")
        
        self._session = session
        self._outbox_repository = outbox_repository
        self._payment_repository = payment_repository
        self._payment_provider = payment_provider
        self._payment_processing_lease_seconds = payment_processing_lease_seconds

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
        processing_token = uuid4()
        processing_expires_at=datetime.now(UTC) + timedelta(seconds=self._payment_processing_lease_seconds)

        async with self._session.begin():
            claimed_payment = await self._payment_repository.claim_for_processing(
                payment_id=payment_id,
                processing_token=processing_token,
                processing_expires_at=processing_expires_at,
            )

            if claimed_payment is None:
                return False

            provider_idempotency_key = claimed_payment.id
            order_id = claimed_payment.order_id
            amount = claimed_payment.amount
            currency = claimed_payment.currency

        payment_result = await self._payment_provider.charge(
            idempotency_key=provider_idempotency_key,
            order_id=order_id,
            amount=amount,
            currency=currency,
        )

        async with self._session.begin():
            payment = await self._payment_repository.get_by_id_for_update(payment_id)
            if payment is None:
                raise ValueError("payment not found")


            await self._session.refresh(payment)

            if (
                payment.status is not PaymentStatus.PROCESSING 
                or payment.processing_token != processing_token
            ):
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
            
        logger.info(
            "payment.status_changed",
            extra={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "target_status": payment.status.value,
            },
        )
        return True
