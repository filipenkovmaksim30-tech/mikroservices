from fastapi import APIRouter, status

from auth_service.routers.dependencies import CurrentUserDependency
from auth_service.schemas.users import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Получить текущего пользователя",
    status_code=status.HTTP_200_OK,
)
async def get_me(current_user: CurrentUserDependency) -> UserRead:
    return UserRead.model_validate(current_user)
