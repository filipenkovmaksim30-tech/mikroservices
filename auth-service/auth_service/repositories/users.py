
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.db.models.users import User, UserStatus


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        result = await self._session.execute(statement)
        user = result.scalar_one_or_none()
        return user

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def block(self, user: User) -> User:
        user.status = UserStatus.BLOCKED
        await self._session.flush()
        return user

    async def active(self, user: User) -> User:
        user.status = UserStatus.ACTIVE
        await self._session.flush()
        return user