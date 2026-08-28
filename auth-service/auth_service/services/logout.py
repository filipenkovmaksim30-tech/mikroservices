

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.security.refresh_tokens import hash_refresh_token

class LogoutService:
    def __init__(
        self,
        session: AsyncSession,
        refresh_repository: RefreshSessionRepository,
    ) -> None:
        self._session = session
        self._refresh_repository = refresh_repository

    async def logout(self, refresh_token: str) -> None:

        refresh_token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)

        async with self._session.begin():
            refresh_session = await self._refresh_repository.get_by_token_hash_for_update(refresh_token_hash)

            if refresh_session is None:
                return
            
            await self._refresh_repository.revoke_family(
                family_id=refresh_session.family_id,
                revoked_at=now,
            )
    