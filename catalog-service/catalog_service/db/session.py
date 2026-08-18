from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from catalog_service.config import Settings

settings = Settings()

async_engine = create_async_engine(url=settings.postgresql_url, echo=True)
async_sessio_factory = async_sessionmaker[AsyncSession](
    bind=async_engine, 
    expire_on_commit=False
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_sessio_factory() as session:
        yield session