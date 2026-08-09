
from uuid import UUID


from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.db.models.processed_events import ProcessedEvent

class ProcessedEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def try_add(
        self, 
        consumer_name: str, 
        event_id: UUID,
        ) -> bool:
        statement = (
            insert(ProcessedEvent)
            .values(
                consumer_name=consumer_name,
                event_id=event_id,
                )
            .on_conflict_do_nothing(
                index_elements=[
                    ProcessedEvent.consumer_name,
                    ProcessedEvent.event_id,
                ],
            )
            .returning(ProcessedEvent.event_id)
        )

        result = await self._session.execute(statement)
        inserted_event_id = result.scalar_one_or_none()
        return inserted_event_id is not None