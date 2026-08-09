from decimal import Decimal
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analytics_service.db.models.base import Base

if TYPE_CHECKING:
    from analytics_service.db.models.analytics_orders import AnalyticsOrder


class AnalyticsOrderItem(Base):
    __tablename__ = "analytics_order_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("analytics_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)

    order: Mapped["AnalyticsOrder"] = relationship(
    back_populates="items",
    )

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_analytics_order_items_unit_price_non_negative"),
        CheckConstraint("quantity > 0", name="ck_analytics_order_items_quantity_positive"),
        UniqueConstraint("order_id", "product_id", name="uq_analytics_order_items_order_product"),
        Index("ix_analytics_order_items_product_id", "product_id"),
    )
