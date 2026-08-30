import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from messaging_lab.db.models.base import Base

if TYPE_CHECKING:
    from messaging_lab.db.models.order_item import OrderItem


class OrderStatus(str, enum.Enum):
    PENDING_STOCK = "pending_stock"
    STOCK_FAILED = "stock_failed"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    receipt_email: Mapped[str] = mapped_column(String(320), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        default=OrderStatus.PENDING_STOCK,
        server_default=OrderStatus.PENDING_STOCK.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_orders_total_amount_non_negative"),
        Index("ix_orders_customer_id", "customer_id"),
    )
