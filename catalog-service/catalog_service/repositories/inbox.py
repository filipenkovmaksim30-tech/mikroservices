
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from catalog_service.db.models.inbox import InboxEvent

class InboxRepository:
    def __init__(
        self,
        session: AsyncSession
    ) -> None:
        self._session = session

    async def try_add(
        self,
        consumer_name: str,
        event_id: UUID,
        event_type: str
    ) -> bool:
        statement = (
            insert(InboxEvent)
            .values(
                consumer_name=consumer_name,
                event_id=event_id,
                event_type=event_type
            )
            .on_conflict_do_nothing(
                index_elements=[
                    InboxEvent.event_id,
                    InboxEvent.consumer_name,
                ],
            )
            .returning(InboxEvent.event_id)
        )
        result = await self._session.execute(statement)
        inserted_event_id = result.scalar_one_or_none()
        return inserted_event_id is not None
    