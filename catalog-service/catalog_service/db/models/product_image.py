
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, Uuid, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_service.db.models.base import Base

if TYPE_CHECKING:
    from catalog_service.db.models.products import Product

class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True),ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    large_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product: Mapped["Product"] = relationship(
        back_populates="images",
    )

    __table_args__ = (
        CheckConstraint("position BETWEEN 0 and 7", name="ck_product_image_position_between_0_and_7"),
        UniqueConstraint("product_id", "position", name="uq_product_id_position", deferrable=True, initially="DEFERRED"),
    )