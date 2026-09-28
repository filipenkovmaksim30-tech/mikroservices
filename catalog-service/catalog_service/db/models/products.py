
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, Index, Uuid, String, Integer, Numeric, DateTime, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_service.db.models.base import Base

if TYPE_CHECKING:
    from catalog_service.db.models.product_image import ProductImage

class Product(Base):
    __tablename__ = "products"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    model_3d_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        lazy="raise",
    )
    __table_args__ = (
        CheckConstraint("price > 0",name="ck_products_price_positive"),
        CheckConstraint("stock_quantity >= 0", name="ck_stock_quantity_non_negative"),
        Index("ix_products_category", "category")
    )


    
