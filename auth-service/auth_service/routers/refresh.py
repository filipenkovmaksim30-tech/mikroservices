from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from auth_service.exceptions import InvalidRefreshTokenError
from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.repositories.users import UserRepository
from auth_service.routers.dependencies import (
    SessionDependency,
    SettingsDependency,
    TokenServiceDependency,
)
from auth_service.schemas.tokens import TokenResponse
from auth_service.services.refresh import RefreshService
from auth_service.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Refresh"])

def get_refresh_service(
    session: SessionDependency,
    token_service: TokenServiceDependency,
    settings: SettingsDependency,
) -> RefreshService:
    return RefreshService(
        session,
        refresh_repository=RefreshSessionRepository(session),
        user_repository=UserRepository(session),
        token_service=token_service,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
    )


RefreshServiceDependency = Annotated[RefreshService, Depends(get_refresh_service)]

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновить refresh-токен",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("20/minute")
async def refresh(
    service: RefreshServiceDependency,
    request: Request,
    response: Response,
    settings: SettingsDependency
) -> TokenResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token is None:
        raise InvalidRefreshTokenError()

    result = await service.refresh(refresh_token)

    remaining_seconds = max(
        0,
        int(
            (
                result.refresh_token_expires_at - datetime.now(UTC)
            ).total_seconds()
        ),
    )

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=result.refresh_token,
        max_age=remaining_seconds,
        expires=result.refresh_token_expires_at,
        path="/auth",
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )

    return result.token_response


