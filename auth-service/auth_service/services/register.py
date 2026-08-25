

from anyio import to_thread

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from auth_service.schemas.users import UserRegister
from auth_service.security.passwords import PasswordHasher
from auth_service.db.models.users import User
from auth_service.repositories.users import UserRepository
from auth_service.exceptions import EmailAlreadyRegisteredError

class RegistrationService:
    def __init__(
        self,
        session: AsyncSession,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._session = session
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def register(self, user_register: UserRegister) -> User:
        email = str(user_register.email).strip().lower()
        password_hash = await to_thread.run_sync(
            self._password_hasher.hash,
            user_register.password
        )
        try:
            async with self._session.begin():
                existing_user = await self._user_repository.get_by_email(email)
                if existing_user is not None:
                    raise EmailAlreadyRegisteredError(email)

                user = User(
                    email=email,
                    password_hash=password_hash
                )
                
                await self._user_repository.add(user)
        except IntegrityError as exc:
            raise EmailAlreadyRegisteredError(email) from exc

        return user
                    

