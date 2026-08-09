from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, SmallInteger, String, Uuid, CheckConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from payment_service.db.models.base import Base

class RabbitMQOutboxEvent(Base):
    __tablename__ = "rabbitmq_outbox_events"
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    aggregate_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "event_version > 0",
            name="ck_rabbitmq_outbox_events_event_version_positive",
        ),
        Index(
            "ix_rabbitmq_outbox_events_unpublished_occurred_at",
            "occurred_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )