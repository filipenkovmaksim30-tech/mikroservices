from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.order import Order, OrderStatus
from messaging_lab.db.models.rabbitmq_outbox import RabbitMQOutboxEvent
from messaging_lab.exceptions import InvalidOrderStockStatusError, OrderNotFoundError
from messaging_lab.messaging.contracts.payments import PaymentRequestedV1
from messaging_lab.messaging.contracts.stock_reservations import (
    StockReservationFailedEnvelopeV1,
    StockReservationResultEnvelopeV1,
    StockReservedEnvelopeV1,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository


class StockReservationResultService:
    def __init__(
        self,
        session: AsyncSession,
        inbox_repository: InboxRepository,
        order_repository: OrderRepository,
        outbox_repository: RabbitMQOutboxRepository,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._inbox_repository = inbox_repository
        self._order_repository = order_repository
        self._outbox_repository = outbox_repository
        self._consumer_name = consumer_name

    def _build_payment_requested_event(self, order: Order) -> RabbitMQOutboxEvent:
        payment_requested = PaymentRequestedV1(
            order_id=order.id,
            amount=order.total_amount,
            currency="RUB",
        )
        payload = payment_requested.model_dump(mode="json")

        return RabbitMQOutboxEvent(
            aggregate_id=order.id,
            event_type="payment.requested",
            event_version=1,
            payload=payload,
        )

    async def process(self, event: StockReservationResultEnvelopeV1) -> bool:
        async with self._session.begin():
            is_new = await self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            order = await self._order_repository.get_by_id_for_update(
                event.payload.order_id
            )

            if order is None:
                raise OrderNotFoundError(event.payload.order_id)

            if isinstance(event, StockReservedEnvelopeV1):
                if order.status in {
                    OrderStatus.PENDING_PAYMENT,
                    OrderStatus.PAID,
                    OrderStatus.PAYMENT_FAILED,
                }:
                    return False

                if order.status is not OrderStatus.PENDING_STOCK:
                    raise InvalidOrderStockStatusError(order.id)

                await self._order_repository.mark_pending_payment(order)

                payment_event = self._build_payment_requested_event(order)
                await self._outbox_repository.add(payment_event)

            elif isinstance(event, StockReservationFailedEnvelopeV1):
                if order.status is OrderStatus.STOCK_FAILED:
                    return False

                if order.status is not OrderStatus.PENDING_STOCK:
                    raise InvalidOrderStockStatusError(order.id)

                await self._order_repository.mark_stock_failed(order)

            return True
