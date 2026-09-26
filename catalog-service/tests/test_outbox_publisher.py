from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.outbox import RabbitMQOutboxEvent
from catalog_service.repositories.outbox import RabbitMQOutboxRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.workers import rabbitmq_outbox as worker_module
from tests.test_reservations_db_integration import product, request_event, reservation_service

pytestmark = pytest.mark.integration
pytest_plugins = ("tests.test_reservations_db_integration",)


async def seed_outbox_event(db_session: AsyncSession) -> RabbitMQOutboxEvent:
    item = product(5)
    async with db_session.begin():
        await ProductRepository(db_session).add(item)
    order_id = uuid4()
    assert await reservation_service(db_session).process(request_event(order_id, {item.id: 1}))
    async with db_session.begin():
        event = await db_session.scalar(
            select(RabbitMQOutboxEvent).where(RabbitMQOutboxEvent.correlation_id == order_id)
        )
    assert event is not None
    return event


async def test_confirmed_publish_marks_outbox_after_send(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = await seed_outbox_event(db_session)
    event_id = event.event_id
    publish = AsyncMock()
    monkeypatch.setattr(worker_module, "publish_message", publish)
    publisher = worker_module.RabbitMQOutboxPublisher(
        db_session, RabbitMQOutboxRepository(db_session), object()
    )

    assert await publisher.publish_batch() == 1
    assert publish.await_args.kwargs["routing_key"] == "stock.reserved"
    async with db_session.begin():
        saved = await db_session.get(RabbitMQOutboxEvent, event_id)
    assert saved.published_at is not None


async def test_failed_publish_leaves_outbox_pending(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = await seed_outbox_event(db_session)
    event_id = event.event_id
    monkeypatch.setattr(
        worker_module, "publish_message", AsyncMock(side_effect=OSError("broker unavailable"))
    )
    publisher = worker_module.RabbitMQOutboxPublisher(
        db_session, RabbitMQOutboxRepository(db_session), object()
    )

    with pytest.raises(OSError, match="broker unavailable"):
        await publisher.publish_batch()

    async with db_session.begin():
        saved = await db_session.get(RabbitMQOutboxEvent, event_id)
    assert saved.published_at is None
