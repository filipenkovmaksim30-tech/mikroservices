import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from catalog_service.db.models import (
    Base,
    Product,
    RabbitMQOutboxEvent,
    StockReservationStatus,
)
from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationConfirmRequestedEnvelopeV1,
    StockReservationConfirmRequestedV1,
    StockReservationReleaseRequestedEnvelopeV1,
    StockReservationReleaseRequestedV1,
    StockReservationRequestedEnvelopeV1,
    StockReservationRequestedV1,
)
from catalog_service.repositories.inbox import InboxRepository
from catalog_service.repositories.outbox import RabbitMQOutboxRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.repositories.reservation import StockReservationRepository
from catalog_service.services.reservation import StockReservationService
from catalog_service.services.reservation_finalization import StockReservationFinalizationService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    raw_url = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("Set CATALOG_TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("CATALOG_TEST_DATABASE_URL must point to a dedicated PostgreSQL *_test DB")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


def product(stock_quantity: int) -> Product:
    return Product(
        id=uuid4(),
        category="books",
        name="Test book",
        description=None,
        price=Decimal("100.00"),
        stock_quantity=stock_quantity,
        is_active=True,
    )


def request_event(
    order_id: UUID, quantities: dict[UUID, int]
) -> StockReservationRequestedEnvelopeV1:
    return StockReservationRequestedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=StockReservationRequestedV1(
            order_id=order_id,
            items=[
                {"product_id": product_id, "quantity": quantity}
                for product_id, quantity in quantities.items()
            ],
        ),
    )


def reservation_service(session: AsyncSession) -> StockReservationService:
    return StockReservationService(
        session=session,
        product_repository=ProductRepository(session),
        reservation_repository=StockReservationRepository(session),
        outbox_repository=RabbitMQOutboxRepository(session),
        inbox_repository=InboxRepository(session),
        consumer_name="reservation-commands-test",
    )


def finalization_service(session: AsyncSession) -> StockReservationFinalizationService:
    return StockReservationFinalizationService(
        session=session,
        inbox_repository=InboxRepository(session),
        reservation_repository=StockReservationRepository(session),
        product_repository=ProductRepository(session),
        consumer_name="reservation-finalization-test",
    )


async def test_reserving_two_products_and_redelivery_decrements_once(
    db_session: AsyncSession,
) -> None:
    first, second = product(10), product(5)
    async with db_session.begin():
        await ProductRepository(db_session).add(first)
        await ProductRepository(db_session).add(second)
    order_id = uuid4()
    event = request_event(order_id, {first.id: 2, second.id: 3})
    service = reservation_service(db_session)

    assert await service.process(event) is True
    assert await service.process(event) is False

    async with db_session.begin():
        reservation = await StockReservationRepository(db_session).get_by_order_id(order_id)
        saved_first = await ProductRepository(db_session).get_by_id(first.id)
        saved_second = await ProductRepository(db_session).get_by_id(second.id)
        outbox_types = (
            await db_session.scalars(
                select(RabbitMQOutboxEvent.event_type).where(
                    RabbitMQOutboxEvent.correlation_id == order_id
                )
            )
        ).all()

    assert reservation is not None
    assert reservation.status is StockReservationStatus.RESERVED
    assert saved_first.stock_quantity == 8
    assert saved_second.stock_quantity == 2
    assert outbox_types == ["stock.reserved"]


async def test_insufficient_second_product_does_not_decrement_first(
    db_session: AsyncSession,
) -> None:
    first, second = product(10), product(1)
    async with db_session.begin():
        await ProductRepository(db_session).add(first)
        await ProductRepository(db_session).add(second)
    order_id = uuid4()

    assert await reservation_service(db_session).process(
        request_event(order_id, {first.id: 2, second.id: 3})
    ) is True

    async with db_session.begin():
        reservation = await StockReservationRepository(db_session).get_by_order_id(order_id)
        saved_first = await ProductRepository(db_session).get_by_id(first.id)
        saved_second = await ProductRepository(db_session).get_by_id(second.id)
        event = await db_session.scalar(
            select(RabbitMQOutboxEvent).where(RabbitMQOutboxEvent.correlation_id == order_id)
        )

    assert reservation is not None
    assert reservation.status is StockReservationStatus.FAILED
    assert reservation.failure_code == "insufficient_stock"
    assert saved_first.stock_quantity == 10
    assert saved_second.stock_quantity == 1
    assert event.event_type == "stock.reservation.failed"


async def test_release_restores_stock_only_once(db_session: AsyncSession) -> None:
    item = product(10)
    async with db_session.begin():
        await ProductRepository(db_session).add(item)
    order_id = uuid4()
    assert await reservation_service(db_session).process(
        request_event(order_id, {item.id: 4})
    ) is True
    event = StockReservationReleaseRequestedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=StockReservationReleaseRequestedV1(order_id=order_id),
    )
    service = finalization_service(db_session)

    assert await service.process(event) is True
    assert await service.process(event) is False

    async with db_session.begin():
        saved = await ProductRepository(db_session).get_by_id(item.id)
        reservation = await StockReservationRepository(db_session).get_by_order_id(order_id)

    assert saved.stock_quantity == 10
    assert reservation.status is StockReservationStatus.RELEASED
    assert reservation.finalized_at is not None


async def test_confirm_keeps_stock_decremented(db_session: AsyncSession) -> None:
    item = product(10)
    async with db_session.begin():
        await ProductRepository(db_session).add(item)
    order_id = uuid4()
    assert await reservation_service(db_session).process(
        request_event(order_id, {item.id: 4})
    ) is True
    event = StockReservationConfirmRequestedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=StockReservationConfirmRequestedV1(order_id=order_id),
    )

    assert await finalization_service(db_session).process(event) is True

    async with db_session.begin():
        saved = await ProductRepository(db_session).get_by_id(item.id)
        reservation = await StockReservationRepository(db_session).get_by_order_id(order_id)

    assert saved.stock_quantity == 6
    assert reservation.status is StockReservationStatus.CONFIRMED
