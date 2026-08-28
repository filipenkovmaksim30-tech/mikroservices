from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.refresh_sessions import RefreshSession
from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.schemas.tokens import TokenResponse
from auth_service.security.refresh_tokens import generate_refresh_token, hash_refresh_token
from auth_service.security.tokens import TokenService
from auth_service.services.authentication import AuthenticationService
from auth_service.services.token_result import IssuedTokens


class LoginService:
    def __init__(
        self,
        session: AsyncSession,
        authentication_service: AuthenticationService,
        token_service: TokenService,
        access_token_expire_minutes: int,
        refresh_repository: RefreshSessionRepository,
        refresh_token_expire_days: int
    ) -> None:
        self._session = session
        self._authentication_service = authentication_service
        self._token_service = token_service
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_repository = refresh_repository
        self._refresh_token_expire_days = refresh_token_expire_days


    async def login(self, email: str, password: str) -> IssuedTokens:
        user = await self._authentication_service.authenticate(email=email, password=password)
        now = datetime.now(UTC)
        access_token = self._token_service.create_access_token(user_id=user.id, role=user.role)
        refresh_token = generate_refresh_token()
        refresh_token_hash = hash_refresh_token(refresh_token)
        refresh_session = RefreshSession(
            user_id=user.id,
            token_hash=refresh_token_hash,
            family_id=uuid4(),
            expires_at=now + timedelta(days=self._refresh_token_expire_days),
        )
        async with self._session.begin():
            await self._refresh_repository.add(refresh_session)

        
        return IssuedTokens(
            token_response=TokenResponse(
                access_token=access_token, 
                expires_in=self._access_token_expire_minutes * 60
            ),
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_session.expires_at,       
        )
