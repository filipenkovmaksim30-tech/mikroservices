from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from auth_service.repositories.users import UserRepository
from auth_service.routers.dependencies import (
    SessionDependency,
    SettingsDependency,
    TokenServiceDependency,
)
from auth_service.schemas.tokens import TokenResponse
from auth_service.security.passwords import PasswordHasher
from auth_service.services.authentication import AuthenticationService
from auth_service.services.login import LoginService


def get_login_service(
    session: SessionDependency,
    token_service: TokenServiceDependency,
    settings: SettingsDependency,
) -> LoginService:
    user_repository = UserRepository(session=session)
    password_hasher = PasswordHasher()
    return LoginService(
        authentication_service=AuthenticationService(
            session=session,
            user_repository=user_repository,
            password_hasher=password_hasher,
        ),
        token_service=token_service,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )

LoginFormDependency = Annotated[OAuth2PasswordRequestForm, Depends()]
LoginServiceDependency = Annotated[LoginService, Depends(get_login_service)]


router = APIRouter(prefix="/auth", tags=["Login"])

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Создание токена и аутентификация",
    status_code=status.HTTP_200_OK,
)
async def login(
    user_form_data: LoginFormDependency,
    service: LoginServiceDependency,
) -> TokenResponse:
    return await service.login(
        email=user_form_data.username,
        password=user_form_data.password,
    )
