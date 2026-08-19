from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.order import Order, OrderStatus


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> Order:
        self._session.add(order)
        await self._session.flush()
        return order

    async def get_by_id(self, order_id: UUID) -> Order | None:
        statement = select(Order).where(Order.id == order_id)
        result = await self._session.execute(statement)
        order = result.scalar_one_or_none()
        return order

    async def mark_paid(self, order: Order) -> Order:
        order.status = OrderStatus.PAID
        await self._session.flush()
        return order

    async def mark_payment_failed(self, order: Order) -> Order:
        order.status = OrderStatus.PAYMENT_FAILED
        await self._session.flush()
        return order