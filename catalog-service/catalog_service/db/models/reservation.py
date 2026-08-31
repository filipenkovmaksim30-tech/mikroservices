from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_service.db.models.base import Base

if TYPE_CHECKING:
    from catalog_service.db.models.reservation_items import StockReservationItem

class StockReservationStatus(StrEnum):
    RESERVED = "reserved"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    FAILED = "failed"

class StockReservation(Base):
    __tablename__ = "stock_reservations"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    status: Mapped[StockReservationStatus] = mapped_column(
        Enum(
            StockReservationStatus,
            name="stock_reservation_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=StockReservationStatus.RESERVED,
        server_default=StockReservationStatus.RESERVED.value,
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list["StockReservationItem"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
