
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.db.models.payments import Payment

from payment_service.repositories.payments import PaymentRepository
from payment_service.repositories.inbox import InboxRepository


from payment_service.messaging.contracts import PaymentRequestedEnvelope

class PaymentProcessingService:
    def __init__(
        self,
        session: AsyncSession,
        payment_repository: PaymentRepository,
        inbox_repository: InboxRepository,
        consumer_name: str,
        ):
        self._session = session
        self._payment_repository = payment_repository
        self._inbox_repository = inbox_repository
        self._consumer_name = consumer_name

    async def process(self, event: PaymentRequestedEnvelope) -> bool:
        async with self._session.begin():
            is_new = self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            #TODO найти payment 
            #TODO проверить наличие payment

            payment = Payment(
                order_id=event.payload.event_id,
                amount=event.payload.amount,
                currency=event.payload.currency,
            )

            await self._payment_repository.add(payment)

        return True