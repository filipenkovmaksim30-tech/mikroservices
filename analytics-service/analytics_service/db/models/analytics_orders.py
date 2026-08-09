from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analytics_service.db.models.base import Base

if TYPE_CHECKING:
    from analytics_service.db.models.analytics_order_items import AnalyticsOrderItem


class AnalyticsOrder(Base):
    __tablename__ = "analytics_orders"

    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    items: Mapped[list["AnalyticsOrderItem"]] = relationship(
    back_populates="order",
    cascade="all, delete-orphan",
    lazy="raise",
)

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_analytics_orders_total_amount_non_negative"),
        Index("ix_analytics_orders_created_at", "created_at"),
        Index(
            "ix_analytics_orders_customer_created_at",
            "customer_id",
            "created_at",
        ),
    )
