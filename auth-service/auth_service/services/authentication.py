from anyio import to_thread

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.users import User, UserStatus
from auth_service.repositories.users import UserRepository
from auth_service.security.passwords import PasswordHasher
from auth_service.exceptions import InvalidCredentialsError, UserBlockedError




class AuthenticationService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._session = session
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def authenticate(self, email: str, password: str) -> User:
        normalize_email = email.strip().lower()
        async with self._session.begin():
            user = await self._user_repository.get_by_email(normalize_email)
            if user is None:
                # TODO: dummy password verification against timing-based user enumeration
                raise InvalidCredentialsError()

        is_valid_password = await to_thread.run_sync(
            self._password_hasher.verify,
            password,
            user.password_hash,
        )

        if is_valid_password is False:
            raise InvalidCredentialsError()

        if user.status is UserStatus.BLOCKED:
            raise UserBlockedError()
        return user
        