from typing import Annotated

from fastapi import Depends, APIRouter, Request, Response, status

from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.routers.dependencies import SessionDependency, SettingsDependency
from auth_service.services.logout import LogoutService


router = APIRouter(prefix="/auth", tags=["Logout"])

def get_logout_service(session: SessionDependency) -> LogoutService:
    return LogoutService(
        session,
        refresh_repository=RefreshSessionRepository(session),
    )

LogoutServiceDependency = Annotated[LogoutService, Depends(get_logout_service)]


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выйти из сессии"
)
async def logout(
    request: Request,
    response: Response,
    service: LogoutServiceDependency,
    settings: SettingsDependency,
) -> None:

    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    if refresh_token is not None:
        await service.logout(refresh_token)

    await service.logout(refresh_token)

    response.delete_cookie(
        key=settings.refresh_cookie_name, 
        path="/auth",
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )
    return None
