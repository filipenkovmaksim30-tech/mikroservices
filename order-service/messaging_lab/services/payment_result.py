

from uuid import UUID

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
from messaging_lab.messaging.contracts.stock_reservations import (
    StockReservationConfirmRequestedV1, 
    StockReservationReleaseRequestedV1,
)
from messaging_lab.db.models.rabbitmq_outbox import RabbitMQOutboxEvent
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.repositories.orders import OrderRepository


class PaymentResultService:
    def __init__(
        self,
        session: AsyncSession,
        inbox_repository: InboxRepository,
        outbox_repository: RabbitMQOutboxRepository,
        order_repository: OrderRepository,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._inbox_repository = inbox_repository
        self._outbox_repository = outbox_repository
        self._order_repository = order_repository
        self._consumer_name = consumer_name

    def _build_confirm_event(self, order_id: UUID) -> RabbitMQOutboxEvent:

        payload = StockReservationConfirmRequestedV1(order_id=order_id)

        return RabbitMQOutboxEvent(
            aggregate_id=order_id,
            event_type="stock.reservation.confirm.requested",
            event_version=1,
            payload=payload.model_dump(mode="json"),
        )

    def _build_release_event(self, order_id: UUID) -> RabbitMQOutboxEvent:

        payload = StockReservationReleaseRequestedV1(order_id=order_id)

        return RabbitMQOutboxEvent(
            aggregate_id=order_id,
            event_type="stock.reservation.release.requested",
            event_version=1,
            payload=payload.model_dump(mode="json"),
        )

    async def process(self, event: PaymentResultEnvelope) -> bool:
        async with self._session.begin():
            is_new = await self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            order = await self._order_repository.get_by_id_for_update(order_id=event.payload.order_id)
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
                confirm_event = self._build_confirm_event(order.id)
                await self._outbox_repository.add(confirm_event)

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
                release_event = self._build_release_event(order.id)
                await self._outbox_repository.add(release_event)
                
            return True
