from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from auth_service.db.models.base import Base


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("refresh_sessions.id", ondelete="SET NULL"), nullable=True)
