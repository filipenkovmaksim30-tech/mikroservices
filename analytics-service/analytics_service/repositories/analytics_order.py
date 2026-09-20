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

    async def get_by_order_id_for_update(self, order_id: UUID) -> AnalyticsOrder | None:
        statement = (
            select(AnalyticsOrder)
            .where(AnalyticsOrder.order_id == order_id)
            .with_for_update()
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> tuple[int, int, int, Decimal, Decimal, int]:
        paid = AnalyticsOrder.paid_at.is_not(None)
        payment_failed = AnalyticsOrder.payment_failed_at.is_not(None)
        orders_statement = (
            select(
                func.count(AnalyticsOrder.order_id).label("orders_count"),
                func.count(AnalyticsOrder.order_id).filter(paid).label("paid_orders_count"),
                func.count(AnalyticsOrder.order_id)
                .filter(payment_failed)
                .label("payment_failed_count"),
                func.coalesce(
                    func.sum(AnalyticsOrder.total_amount).filter(paid),
                    Decimal("0"),
                ).label("revenue"),
                func.coalesce(
                    cast(
                        func.avg(AnalyticsOrder.total_amount).filter(paid),
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
            .where(paid)
        )
        items_result = await self._session.execute(items_statement)
        items_quantity = items_result.scalar_one()

        return (
            orders_summary.orders_count,
            orders_summary.paid_orders_count,
            orders_summary.payment_failed_count,
            orders_summary.revenue,
            orders_summary.average_order_value,
            items_quantity,
        )

    async def get_daily_summary(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[tuple[date, int, int, int, Decimal, Decimal, int]]:
        day_expression = func.date(func.timezone("UTC", AnalyticsOrder.created_at)).label("day")
        paid = AnalyticsOrder.paid_at.is_not(None)
        payment_failed = AnalyticsOrder.payment_failed_at.is_not(None)

        orders_statement = (
            select(
                day_expression,
                func.count(AnalyticsOrder.order_id).label("orders_count"),
                func.count(AnalyticsOrder.order_id).filter(paid).label("paid_orders_count"),
                func.count(AnalyticsOrder.order_id)
                .filter(payment_failed)
                .label("payment_failed_count"),
                func.coalesce(
                    func.sum(AnalyticsOrder.total_amount).filter(paid),
                    Decimal("0"),
                ).label("revenue"),
                func.coalesce(
                    cast(
                        func.avg(AnalyticsOrder.total_amount).filter(paid),
                        Numeric(precision=18, scale=2),
                    ),
                    Decimal("0"),
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
            .where(paid)
            .group_by(day_expression)
        )
        items_result = await self._session.execute(items_statement)
        daily_items = items_result.all()

        items_by_day = {row.day: row.items_quantity for row in daily_items}

        return [
            (
                row.day,
                row.orders_count,
                row.paid_orders_count,
                row.payment_failed_count,
                row.revenue,
                row.average_order_value,
                items_by_day.get(row.day, 0),
            )
            for row in daily_orders
        ]
