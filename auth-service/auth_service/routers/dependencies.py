from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config import Settings
from auth_service.db.models.users import User, UserRole
from auth_service.db.session import get_session
from auth_service.repositories.users import UserRepository
from auth_service.security.tokens import TokenService
from auth_service.services.current_user import CurrentUserService
from auth_service.exceptions import PermissionDeniedError

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    settings = get_settings()

    private_key = settings.jwt_private_key_path.read_text(encoding="utf-8")
    public_key = settings.jwt_public_key_path.read_text(encoding="utf-8")


    return TokenService(
        private_key=private_key,
        public_key=public_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
TokenServiceDependency = Annotated[TokenService, Depends(get_token_service)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
AccessTokenDependency = Annotated[str, Depends(oauth2_scheme)]


def get_current_user_service(
    session: SessionDependency,
    token_service: TokenServiceDependency,
) -> CurrentUserService:
    return CurrentUserService(
        session=session,
        user_repository=UserRepository(session=session),
        token_service=token_service,
    )


CurrentUserServiceDependency = Annotated[CurrentUserService, Depends(get_current_user_service)]

async def get_current_user(
    token: AccessTokenDependency,
    service: CurrentUserServiceDependency,
) -> User:
    return await service.get_current_user(access_token=token)

CurrentUserDependency = Annotated[User, Depends(get_current_user)]

async def get_current_admin(
    current_user: CurrentUserDependency
) -> User:
    if current_user.role is not UserRole.ADMIN:
        raise PermissionDeniedError()
    return current_user

CurrentAdminDependency = Annotated[User, Depends(get_current_admin)]
