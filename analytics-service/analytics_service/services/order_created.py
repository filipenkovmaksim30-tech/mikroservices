from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.db.models.analytics_order_items import AnalyticsOrderItem
from analytics_service.db.models.analytics_orders import AnalyticsOrder
from analytics_service.messaging.contract import AnalyticsEventEnvelope, OrderCreatedAnalyticsV1
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.repositories.processed_event import ProcessedEventRepository


class OrderCreatedAnalyticsService:
    def __init__(
        self,
        session: AsyncSession,
        processed_event_repository: ProcessedEventRepository,
        analytics_order_repository: AnalyticsOrderRepository,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._processed_event_repository = processed_event_repository
        self._analytics_order_repository = analytics_order_repository
        self._consumer_name = consumer_name

    async def process(self, event: AnalyticsEventEnvelope[OrderCreatedAnalyticsV1]) -> bool:
        async with self._session.begin():
            is_new = await self._processed_event_repository.try_add(
                consumer_name=self._consumer_name, event_id=event.event_id
            )
            if not is_new:
                return False
            order_items = [
                AnalyticsOrderItem(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                for item in event.payload.items
            ]

            analytics_order = AnalyticsOrder(
                order_id=event.payload.order_id,
                customer_id=event.payload.customer_id,
                total_amount=event.payload.total_amount,
                created_at=event.occurred_at,
                items=order_items,
            )
            await self._analytics_order_repository.add(analytics_order)
        return True
