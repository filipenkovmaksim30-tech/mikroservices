from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_service.db.models.base import Base

if TYPE_CHECKING:
    from catalog_service.db.models.reservation import StockReservation


class StockReservationItem(Base):
    __tablename__ = "stock_reservation_items"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    reservation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stock_reservations.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation: Mapped["StockReservation"] = relationship(
        back_populates="items",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_stock_reservation_items_quantity_positive",
        ),
        UniqueConstraint(
            "reservation_id",
            "product_id",
            name="uq_stock_reservation_items_reservation_product",
        )
    )
