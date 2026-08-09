from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.db.models.analytics_orders import AnalyticsOrder
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.schemas.analytics import AnalyticsSummaryResponse, DailySummaryResponse
from analytics_service.exceptions import InvalidAnalyticsPeriodError


class AnalyticsOrderService:
    def __init__(
        self,
        analytics_order_repository: AnalyticsOrderRepository,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._analytics_order_repository = analytics_order_repository

    async def get_by_id(self, order_id: UUID) -> AnalyticsOrder | None:
        async with self._session.begin():
            return await self._analytics_order_repository.get_by_order_id(order_id)

    async def get_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> AnalyticsSummaryResponse:
        self._validate_period(date_from, date_to)

        async with self._session.begin():
            (
                orders_count,
                revenue,
                average_order_value,
                items_quantity,
            ) = await self._analytics_order_repository.get_summary(date_from, date_to)

        return AnalyticsSummaryResponse(
            orders_count=orders_count,
            revenue=revenue,
            average_order_value=average_order_value,
            items_quantity=items_quantity,
        )

    async def get_daily_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[DailySummaryResponse]:
        self._validate_period(date_from, date_to)

        async with self._session.begin():
            daily_rows = await self._analytics_order_repository.get_daily_summary(
                date_from=date_from,
                date_to=date_to,
            )

        return [
            DailySummaryResponse(
                day=day,
                orders_count=orders_count,
                revenue=revenue,
                average_order_value=average_order_value,
                items_quantity=items_quantity,
            )
            for (
                day,
                orders_count,
                revenue,
                average_order_value,
                items_quantity,
            ) in daily_rows
        ]

    @staticmethod
    def _validate_period(
        date_from: datetime,
        date_to: datetime,
    ) -> None:
        dates = (date_from, date_to)

        if any(
            value.tzinfo is None or value.utcoffset() is None
            for value in dates
        ):
            raise InvalidAnalyticsPeriodError(
                "date_from and date_to must contain timezone information"
            )

        if date_from >= date_to:
            raise InvalidAnalyticsPeriodError(
                "date_from must be earlier than date_to"
            )
