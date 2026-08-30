

from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.order import OrderStatus
from messaging_lab.exceptions import (
    InvalidOrderPaymentStatusError,
    OrderNotFoundError,
    PaymentAmountMismatchError,
)
from messaging_lab.messaging.contracts.payments import (
    PaymentFailedEnvelope,
    PaymentResultEnvelope,
    PaymentSucceededEnvelope,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository


class PaymentResultService:
    def __init__(
        self,
        session: AsyncSession,
        inbox_repository: InboxRepository,
        order_repository: OrderRepository,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._inbox_repository = inbox_repository
        self._order_repository = order_repository
        self._consumer_name = consumer_name

    async def process(self, event: PaymentResultEnvelope) -> bool:
        async with self._session.begin():
            is_new = await self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            order = await self._order_repository.get_by_id(order_id=event.payload.order_id)
            if order is None:
                raise OrderNotFoundError(order_id=event.payload.order_id)

            if order.total_amount != event.payload.amount:
                raise PaymentAmountMismatchError(
                    order_id=order.id,
                    expected_amount=order.total_amount,
                    actual_amount=event.payload.amount,
                )

            if isinstance(event, PaymentSucceededEnvelope):
                if order.status is OrderStatus.PAID:
                    return False

                if order.status is not OrderStatus.PENDING_PAYMENT:
                    raise InvalidOrderPaymentStatusError(
                        order_id=order.id,
                        current_order_status=order.status.value,
                        target_order_status=OrderStatus.PAID.value,
                    )

                await self._order_repository.mark_paid(order=order)

            elif isinstance(event, PaymentFailedEnvelope):
                if order.status is OrderStatus.PAYMENT_FAILED:
                    return False

                if order.status is not OrderStatus.PENDING_PAYMENT:
                    raise InvalidOrderPaymentStatusError(
                        order_id=order.id,
                        current_order_status=order.status.value,
                        target_order_status=OrderStatus.PAYMENT_FAILED.value,
                    )

                await self._order_repository.mark_payment_failed(order=order)

            return True
