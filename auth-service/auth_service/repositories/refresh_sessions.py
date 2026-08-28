
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.refresh_sessions import RefreshSession


class RefreshSessionRepository:
    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session

    async def add(self, refresh_session: RefreshSession) -> RefreshSession:
        self._session.add(refresh_session)
        await self._session.flush()
        return refresh_session

    async def get_by_token_hash_for_update(self, token_hash: str) -> RefreshSession | None:
        statement = (
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke(
        self,
        refresh_session: RefreshSession,
        revoked_at: datetime,
        replaced_by_session_id: UUID | None = None
    ) -> RefreshSession:
        refresh_session.revoked_at = revoked_at
        refresh_session.replaced_by_session_id = replaced_by_session_id
        await self._session.flush()
        return refresh_session

    async def revoke_family(
        self,
        family_id: UUID,
        revoked_at: datetime,
    ) -> int:
        statement = (
            update(RefreshSession)
            .where(
                RefreshSession.family_id == family_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        result = await self._session.execute(statement)
        return result.rowcount