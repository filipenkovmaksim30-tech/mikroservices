from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from catalog_service.db.models.reservation import StockReservation, StockReservationStatus


class StockReservationRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(self, reservation: StockReservation) -> StockReservation:
        self._session.add(reservation)
        await self._session.flush()
        return reservation

    async def get_by_order_id(self, order_id: UUID) -> StockReservation | None:
        statement = select(StockReservation).where(StockReservation.order_id == order_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, reservation_id: UUID) -> StockReservation | None:
        statement = (
            select(StockReservation).where(StockReservation.id == reservation_id).with_for_update()
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_order_id_for_update(self, order_id: UUID) -> StockReservation | None:
        statement = (
            select(StockReservation)
            .where(StockReservation.order_id == order_id)
            .with_for_update()
            .options(selectinload(StockReservation.items))
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def mark_confirmed(
        self, reservation: StockReservation, finalized_at: datetime
    ) -> StockReservation:
        reservation.status = StockReservationStatus.CONFIRMED
        reservation.finalized_at = finalized_at
        await self._session.flush()
        return reservation

    async def mark_released(
        self, reservation: StockReservation, finalized_at: datetime
    ) -> StockReservation:
        reservation.status = StockReservationStatus.RELEASED
        reservation.finalized_at = finalized_at
        await self._session.flush()
        return reservation
