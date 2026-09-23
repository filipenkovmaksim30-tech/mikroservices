from datetime import datetime

from sqlalchemy import exists, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from messaging_lab.db.models import KafkaOutboxEvent


class KafkaOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: KafkaOutboxEvent) -> KafkaOutboxEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_unpublished_batch(self, limit: int) -> list[KafkaOutboxEvent]:
        earlier_event = aliased(KafkaOutboxEvent)
        has_earlier_unpublished = exists(
            select(1).where(
                earlier_event.aggregate_id == KafkaOutboxEvent.aggregate_id,
                earlier_event.published_at.is_(None),
                tuple_(
                    earlier_event.occurred_at,
                    earlier_event.event_id,
                )
                < tuple_(KafkaOutboxEvent.occurred_at, KafkaOutboxEvent.event_id),
            )
        ).correlate(KafkaOutboxEvent)
        statement = (
            select(KafkaOutboxEvent)
            .where(
                KafkaOutboxEvent.published_at.is_(None),
                ~has_earlier_unpublished,
            )
            .order_by(
                KafkaOutboxEvent.occurred_at,
                KafkaOutboxEvent.event_id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def mark_as_published(self, event: KafkaOutboxEvent, published_at: datetime) -> None:
        event.published_at = published_at
        await self._session.flush()
