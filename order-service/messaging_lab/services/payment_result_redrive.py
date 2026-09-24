from dataclasses import dataclass
from enum import StrEnum

from messaging_lab.db.models.order import OrderStatus
from messaging_lab.messaging.contracts.payments import (
    PaymentFailedEnvelope,
    PaymentResultEnvelope,
    PaymentSucceededEnvelope,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.orders import OrderRepository


class RedriveStatus(StrEnum):
    READY = "ready"
    ALREADY_PROCESSED = "already_processed"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class RedriveDecision:
    status: RedriveStatus
    reason: str


class PaymentResultRedriveService:
    def __init__(
        self,
        order_repository: OrderRepository,
        inbox_repository: InboxRepository,
        consumer_name: str,
    ) -> None:
        self._order_repository = order_repository
        self._inbox_repository = inbox_repository
        self._consumer_name = consumer_name

    async def inspect(self, event: PaymentResultEnvelope) -> RedriveDecision:
        already_processed = await self._inbox_repository.exists(
            consumer_name=self._consumer_name,
            event_id=event.event_id,
        )
        if already_processed:
            return RedriveDecision(
                status=RedriveStatus.ALREADY_PROCESSED,
                reason="Event already exists in Inbox",
            )

        order = await self._order_repository.get_by_id(
            order_id=event.payload.order_id,
        )
        if order is None:
            return RedriveDecision(
                status=RedriveStatus.CONFLICT,
                reason="Order not found",
            )

        if order.total_amount != event.payload.amount:
            return RedriveDecision(
                status=RedriveStatus.CONFLICT,
                reason="Payment amount does not match order total",
            )

        if isinstance(event, PaymentSucceededEnvelope):
            if order.status == OrderStatus.PENDING_PAYMENT:
                return RedriveDecision(
                    status=RedriveStatus.READY,
                    reason="Order is ready to accept successful payment",
                )
            if order.status == OrderStatus.PAID:
                return RedriveDecision(
                    status=RedriveStatus.ALREADY_PROCESSED,
                    reason="Order is already paid",
                )
            return RedriveDecision(
                status=RedriveStatus.CONFLICT,
                reason=(f"Cannot apply payment success to order status {order.status.value}"),
            )

        if isinstance(event, PaymentFailedEnvelope):
            if order.status == OrderStatus.PENDING_PAYMENT:
                return RedriveDecision(
                    status=RedriveStatus.READY,
                    reason="Order is ready to accept failed payment",
                )
            if order.status == OrderStatus.PAYMENT_FAILED:
                return RedriveDecision(
                    status=RedriveStatus.ALREADY_PROCESSED,
                    reason="Order is already marked as payment failed",
                )
            return RedriveDecision(
                status=RedriveStatus.CONFLICT,
                reason=(f"Cannot apply payment failure to order status {order.status.value}"),
            )

        return RedriveDecision(
            status=RedriveStatus.CONFLICT,
            reason=f"Unsupported event type: {type(event).__name__}",
        )
