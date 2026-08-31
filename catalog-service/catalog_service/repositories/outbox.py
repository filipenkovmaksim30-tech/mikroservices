
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.outbox import RabbitMQOutboxEvent

class RabbitMQOutboxRepository:
    def __init__(
        self,
        session: AsyncSession
    ) -> None:
        self._session = session

    async def add(self, event: RabbitMQOutboxEvent) -> RabbitMQOutboxEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_unpublished_batch(self, limit: int) -> list[RabbitMQOutboxEvent]:
        statement = (
            select(RabbitMQOutboxEvent)
            .where(RabbitMQOutboxEvent.published_at.is_(None))
            .order_by(RabbitMQOutboxEvent.occurred_at, RabbitMQOutboxEvent.event_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())


    async def mark_as_published(self, event: RabbitMQOutboxEvent, published_at: datetime) -> None:
        event.published_at = published_at
        await self._session.flush()
