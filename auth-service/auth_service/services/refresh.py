import enum
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.refresh_sessions import RefreshSession
from auth_service.db.models.users import User, UserStatus
from auth_service.exceptions import (
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
    UserBlockedError,
)
from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.repositories.users import UserRepository
from auth_service.schemas.tokens import TokenResponse
from auth_service.security.refresh_tokens import (
    generate_refresh_token,
    hash_refresh_token,
)
from auth_service.security.tokens import TokenService
from auth_service.services.token_result import IssuedTokens


class _RefreshFailure(enum.Enum):
    REUSE_DETECTED = enum.auto()
    USER_BLOCKED = enum.auto()


class RefreshService:
    def __init__(
        self,
        session: AsyncSession,
        refresh_repository: RefreshSessionRepository,
        user_repository: UserRepository,
        token_service: TokenService,
        access_token_expire_minutes: int,
    ) -> None:
        self._session = session
        self._refresh_repository = refresh_repository
        self._user_repository = user_repository
        self._token_service = token_service
        self._access_token_expire_minutes = access_token_expire_minutes

    def _validate_expiration(
        self,
        refresh_session: RefreshSession,
        now: datetime,
    ) -> None:
        if refresh_session.expires_at <= now:
            raise InvalidRefreshTokenError()

    def _build_rotated_session(
        self,
        old_session: RefreshSession,
        token_hash: str,
    ) -> RefreshSession:
        return RefreshSession(
            user_id=old_session.user_id,
            token_hash=token_hash,
            family_id=old_session.family_id,
            expires_at=old_session.expires_at,
        )

    def _build_issued_tokens(
        self,
        user: User,
        refresh_token: str,
        refresh_token_expires_at: datetime,
    ) -> IssuedTokens:
        access_token = self._token_service.create_access_token(
            user_id=user.id,
            role=user.role,
        )
        return IssuedTokens(
            token_response=TokenResponse(
                access_token=access_token,
                expires_in=self._access_token_expire_minutes * 60,
            ),
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_token_expires_at,
        )

    async def _refresh_in_transaction(
        self,
        token_hash: str,
        now: datetime,
    ) -> IssuedTokens | _RefreshFailure:
        async with self._session.begin():
            old_session = await self._refresh_repository.get_by_token_hash_for_update(token_hash)

            if old_session is None:
                raise InvalidRefreshTokenError()

            self._validate_expiration(refresh_session=old_session, now=now)

            if old_session.revoked_at is not None:
                await self._refresh_repository.revoke_family(
                    family_id=old_session.family_id,
                    revoked_at=now,
                )
                return _RefreshFailure.REUSE_DETECTED

            user = await self._user_repository.get_by_id(old_session.user_id)
            if user is None:
                raise InvalidRefreshTokenError()

            if user.status is UserStatus.BLOCKED:
                await self._refresh_repository.revoke_family(
                    family_id=old_session.family_id,
                    revoked_at=now,
                )
                return _RefreshFailure.USER_BLOCKED

            new_refresh_token = generate_refresh_token()
            new_token_hash = hash_refresh_token(new_refresh_token)
            new_session = self._build_rotated_session(
                old_session=old_session,
                token_hash=new_token_hash,
            )
            created_session = await self._refresh_repository.add(new_session)

            await self._refresh_repository.revoke(
                refresh_session=old_session,
                revoked_at=now,
                replaced_by_session_id=created_session.id,
            )

            return self._build_issued_tokens(
                user=user,
                refresh_token=new_refresh_token,
                refresh_token_expires_at=created_session.expires_at,
            )

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        result = await self._refresh_in_transaction(
            token_hash=hash_refresh_token(refresh_token),
            now=datetime.now(UTC),
        )

        if isinstance(result, IssuedTokens):
            return result

        if result is _RefreshFailure.REUSE_DETECTED:
            raise RefreshTokenReuseError()

        raise UserBlockedError()
