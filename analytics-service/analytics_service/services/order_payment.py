from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.exceptions import (
    AnalyticsOrderDataMismatchError,
    ConflictingAnalyticsPaymentResultError,
    OrderNotFoundError,
)
from analytics_service.messaging.contract import (
    AnalyticsOrderPaidEnvelopeV1,
    AnalyticsOrderPaymentEnvelopeV1,
    AnalyticsOrderPaymentFailedEnvelopeV1,
)
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.repositories.processed_event import ProcessedEventRepository


class AnalyticPaymentService:
    def __init__(
        self,
        session: AsyncSession,
        processed_repository: ProcessedEventRepository,
        analytics_order_repository: AnalyticsOrderRepository,
        consumer_name: str,
    ):
        self._session = session
        self._processed_repository = processed_repository
        self._analytics_order_repository = analytics_order_repository
        self._consumer_name = consumer_name

    async def process(self, event: AnalyticsOrderPaymentEnvelopeV1) -> bool:
        async with self._session.begin():
            is_new = await self._processed_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
            )
            if not is_new:
                return False

            order = await self._analytics_order_repository.get_by_order_id_for_update(
                event.payload.order_id
            )
            if order is None:
                raise OrderNotFoundError(event.payload.order_id)

            if order.customer_id != event.payload.customer_id:
                raise AnalyticsOrderDataMismatchError(order.order_id, "customer_id")
            if order.total_amount != event.payload.total_amount:
                raise AnalyticsOrderDataMismatchError(order.order_id, "total_amount")

            if isinstance(event, AnalyticsOrderPaidEnvelopeV1):
                if order.payment_failed_at is not None:
                    raise ConflictingAnalyticsPaymentResultError(order.order_id)
                if order.paid_at is not None:
                    if order.paid_at != event.payload.paid_at:
                        raise ConflictingAnalyticsPaymentResultError(order.order_id)
                    return False
                order.paid_at = event.payload.paid_at

            elif isinstance(event, AnalyticsOrderPaymentFailedEnvelopeV1):
                if order.paid_at is not None:
                    raise ConflictingAnalyticsPaymentResultError(order.order_id)
                if order.payment_failed_at is not None:
                    if order.payment_failed_at != event.payload.failed_at:
                        raise ConflictingAnalyticsPaymentResultError(order.order_id)
                    return False
                order.payment_failed_at = event.payload.failed_at

            else:
                raise TypeError(f"Unsupported analytics payment event: {type(event).__name__}")
        return True
