from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.session import get_session
from auth_service.schemas.users import UserRegister, UserRead
from auth_service.repositories.users import UserRepository
from auth_service.services.register import RegistrationService
from auth_service.security.passwords import PasswordHasher

SessionDependency = Annotated[AsyncSession, Depends(get_session)]

async def get_register_service(session: SessionDependency):
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
    description="Регистрация пользователей",
)
async def register(
    service: ServiceDependency,
    user_data: UserRegister,
) -> UserRead:
    return await service.register(user_register=user_data)