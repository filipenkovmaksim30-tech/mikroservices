
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.users import User, UserStatus
from auth_service.exceptions import InvalidAccessTokenError, UserBlockedError
from auth_service.repositories.users import UserRepository
from auth_service.security.tokens import TokenService


class CurrentUserService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        token_service: TokenService,
    ) -> None:
        self._session = session
        self._user_repository = user_repository
        self._token_service = token_service

    async def get_current_user(self, access_token: str) -> User:
        payload = self._token_service.decode_access_token(access_token)
        async with self._session.begin():
            user = await self._user_repository.get_by_id(payload.sub)

            if user is None:
                raise InvalidAccessTokenError()

            if user.status is UserStatus.BLOCKED:
                raise UserBlockedError()

        return user
