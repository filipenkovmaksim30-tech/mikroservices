
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


from payment_service.config import Settings

settings = Settings()


async_engine = create_async_engine(url=settings.postgresql_url)
async_session_factory = async_sessionmaker(bind=async_engine, expire_on_commit=False)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session