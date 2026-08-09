from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from analytics_service.db.models.analytics_order_items import AnalyticsOrderItem
from analytics_service.db.models.analytics_orders import AnalyticsOrder


class AnalyticsOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, analytics_order: AnalyticsOrder) -> AnalyticsOrder:
        self._session.add(analytics_order)
        await self._session.flush()
        return analytics_order

    async def get_by_order_id(self, order_id: UUID) -> AnalyticsOrder | None:
        statement = (
            select(AnalyticsOrder)
            .where(AnalyticsOrder.order_id == order_id)
            .options(selectinload(AnalyticsOrder.items))
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> tuple[int, Decimal, Decimal, int]:
        orders_statement = (
            select(
                func.count(AnalyticsOrder.order_id).label("orders_count"),
                func.coalesce(
                    func.sum(AnalyticsOrder.total_amount),
                    Decimal("0"),
                ).label("revenue"),
                func.coalesce(
                    cast(
                        func.avg(AnalyticsOrder.total_amount),
                        Numeric(precision=18, scale=2),
                    ),
                    Decimal("0"),
                ).label("average_order_value"),
            )
            .where(AnalyticsOrder.created_at >= date_from)
            .where(AnalyticsOrder.created_at < date_to)
        )
        orders_result = await self._session.execute(orders_statement)
        orders_summary = orders_result.one()

        items_statement = (
            select(func.coalesce(func.sum(AnalyticsOrderItem.quantity), 0).label("items_quantity"))
            .join(
                AnalyticsOrder,
                AnalyticsOrder.order_id == AnalyticsOrderItem.order_id,
            )
            .where(AnalyticsOrder.created_at >= date_from)
            .where(AnalyticsOrder.created_at < date_to)
        )
        items_result = await self._session.execute(items_statement)
        items_quantity = items_result.scalar_one()

        return (
            orders_summary.orders_count,
            orders_summary.revenue,
            orders_summary.average_order_value,
            items_quantity,
        )

    async def get_daily_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[tuple[date, int, Decimal, Decimal, int]]:
        day_expression = func.date(func.timezone("UTC", AnalyticsOrder.created_at)).label("day")

        orders_statement = (
            select(
                day_expression,
                func.count(AnalyticsOrder.order_id).label("orders_count"),
                func.sum(AnalyticsOrder.total_amount).label("revenue"),
                cast(
                    func.avg(AnalyticsOrder.total_amount),
                    Numeric(precision=18, scale=2),
                ).label("average_order_value"),
            )
            .where(AnalyticsOrder.created_at >= date_from)
            .where(AnalyticsOrder.created_at < date_to)
            .group_by(day_expression)
            .order_by(day_expression)
        )
        orders_result = await self._session.execute(orders_statement)
        daily_orders = orders_result.all()

        items_statement = (
            select(
                day_expression,
                func.sum(AnalyticsOrderItem.quantity).label("items_quantity"),
            )
            .join(
                AnalyticsOrder,
                AnalyticsOrder.order_id == AnalyticsOrderItem.order_id,
            )
            .where(AnalyticsOrder.created_at >= date_from)
            .where(AnalyticsOrder.created_at < date_to)
            .group_by(day_expression)
        )
        items_result = await self._session.execute(items_statement)
        daily_items = items_result.all()

        items_by_day = {row.day: row.items_quantity for row in daily_items}

        return [
            (
                row.day,
                row.orders_count,
                row.revenue,
                row.average_order_value,
                items_by_day.get(row.day, 0),
            )
            for row in daily_orders
        ]
