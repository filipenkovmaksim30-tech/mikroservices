from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from auth_service.repositories.users import UserRepository
from auth_service.routers.dependencies import SessionDependency
from auth_service.schemas.users import UserRead, UserRegister
from auth_service.security.passwords import PasswordHasher
from auth_service.services.register import RegistrationService
from auth_service.rate_limit import limiter


def get_register_service(session: SessionDependency) -> RegistrationService:
    return RegistrationService(
        session=session,
        user_repository=UserRepository(session),
        password_hasher=PasswordHasher(),
    )

ServiceDependency = Annotated[RegistrationService, Depends(get_register_service)]

router = APIRouter(prefix="/auth", tags=["Registration"])

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пользователей",
)
@limiter.limit("3/minute")
async def register(
    service: ServiceDependency,
    user_data: UserRegister,
    request: Request,
) -> UserRead:
    user = await service.register(user_register=user_data)
    return UserRead.model_validate(user)
