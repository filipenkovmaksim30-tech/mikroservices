from typing import Annotated

from fastapi import Depends, APIRouter, status
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.routers.dependencies import get_settings, get_token_service
from auth_service.schemas.tokens import TokenResponse
from auth_service.config import Settings
from auth_service.security.passwords import PasswordHasher
from auth_service.repositories.users import UserRepository
from auth_service.security.tokens import TokenService
from auth_service.services.authentication import AuthenticationService
from auth_service.services.login import LoginService
from auth_service.db.session import get_session

SessionDependency = Annotated[AsyncSession, Depends(get_session)]

TokenDependency = Annotated[TokenService, Depends(get_token_service)]

SettingsDependency = Annotated[Settings, Depends(get_settings)]

LoginFormDependency = Annotated[OAuth2PasswordRequestForm, Depends()]

def get_login_service(
    session: SessionDependency,
    token_service: TokenDependency,
    settings: SettingsDependency
) -> LoginService:
    user_repository = UserRepository(session=session)
    password_hasher = PasswordHasher()
    return LoginService(
        authentication_service = AuthenticationService(
            session=session,
            user_repository=user_repository,
            password_hasher=password_hasher
        ),
        token_service=token_service,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )

LoginserviceDependency = Annotated[LoginService, Depends(get_login_service)]


router = APIRouter(prefix="/auth", tags=["Login"])

@router.post(
    "/token",
    response_model=TokenResponse,
    description="Создание токена и аутенфикация",
    status_code=status.HTTP_200_OK
)
async def login(
    user_form_data: LoginFormDependency,
    service: LoginserviceDependency,
) -> TokenResponse:
    return await service.login(email=user_form_data.username, password=user_form_data.password)