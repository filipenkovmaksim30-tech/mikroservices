import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from analytics_service.db.models import AnalyticsOrder, Base, ProcessedEvent
from analytics_service.exceptions import OrderNotFoundError
from analytics_service.messaging.contract import (
    AnalyticsEventEnvelope,
    AnalyticsOrderPaidEnvelopeV1,
    AnalyticsOrderPaidV1,
    OrderCreatedAnalyticsV1,
)
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.repositories.processed_event import ProcessedEventRepository
from analytics_service.services.analytics_orders import AnalyticsOrderService
from analytics_service.services.order_created import OrderCreatedAnalyticsService
from analytics_service.services.order_payment import AnalyticPaymentService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    raw_url = os.environ.get("ANALYTICS_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("Set ANALYTICS_TEST_DATABASE_URL to a dedicated PostgreSQL *_test DB")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("ANALYTICS_TEST_DATABASE_URL must point to a dedicated PostgreSQL *_test DB")

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


def created_event(
    order_id: UUID, customer_id: UUID, occurred_at: datetime, *, two_items: bool = False
) -> AnalyticsEventEnvelope[OrderCreatedAnalyticsV1]:
    items = [{"product_id": uuid4(), "quantity": 2, "unit_price": "50.00"}]
    if two_items:
        items.append({"product_id": uuid4(), "quantity": 1, "unit_price": "100.00"})
    return AnalyticsEventEnvelope[OrderCreatedAnalyticsV1](
        event_id=uuid4(),
        event_type="order.created",
        event_version=1,
        occurred_at=occurred_at,
        correlation_id=order_id,
        payload=OrderCreatedAnalyticsV1(
            order_id=order_id,
            customer_id=customer_id,
            total_amount=Decimal("200.00" if two_items else "100.00"),
            items=items,
        ),
    )


def paid_event(
    order_id: UUID, customer_id: UUID, amount: Decimal, occurred_at: datetime
) -> AnalyticsOrderPaidEnvelopeV1:
    return AnalyticsOrderPaidEnvelopeV1(
        event_id=uuid4(),
        occurred_at=occurred_at,
        correlation_id=order_id,
        payload=AnalyticsOrderPaidV1(
            order_id=order_id,
            customer_id=customer_id,
            total_amount=amount,
            currency="RUB",
            paid_at=occurred_at,
        ),
    )


def creation_service(session: AsyncSession) -> OrderCreatedAnalyticsService:
    return OrderCreatedAnalyticsService(
        session=session,
        processed_event_repository=ProcessedEventRepository(session),
        analytics_order_repository=AnalyticsOrderRepository(session),
        consumer_name="analytics-test",
    )


def payment_service(session: AsyncSession) -> AnalyticPaymentService:
    return AnalyticPaymentService(
        session=session,
        processed_repository=ProcessedEventRepository(session),
        analytics_order_repository=AnalyticsOrderRepository(session),
        consumer_name="analytics-test",
    )


async def test_redelivery_creates_one_analytics_order(db_session: AsyncSession) -> None:
    order_id = uuid4()
    event = created_event(order_id, uuid4(), datetime.now(UTC))
    service = creation_service(db_session)

    assert await service.process(event) is True
    assert await service.process(event) is False

    async with db_session.begin():
        order_count = await db_session.scalar(
            select(func.count())
            .select_from(AnalyticsOrder)
            .where(AnalyticsOrder.order_id == order_id)
        )
        processed_count = await db_session.scalar(
            select(func.count())
            .select_from(ProcessedEvent)
            .where(ProcessedEvent.event_id == event.event_id)
        )

    assert order_count == 1
    assert processed_count == 1


async def test_summary_counts_paid_revenue_once_with_multiple_items(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    customer_id = uuid4()
    paid_order_id = uuid4()
    unpaid_order_id = uuid4()
    creator = creation_service(db_session)
    assert await creator.process(created_event(paid_order_id, customer_id, now, two_items=True))
    assert await creator.process(created_event(unpaid_order_id, customer_id, now))
    assert await payment_service(db_session).process(
        paid_event(paid_order_id, customer_id, Decimal("200.00"), now)
    )

    summary = await AnalyticsOrderService(
        AnalyticsOrderRepository(db_session), db_session
    ).get_summary(now - timedelta(days=1), now + timedelta(days=1))

    assert summary.orders_count == 2
    assert summary.paid_orders_count == 1
    assert summary.payment_failed_count == 0
    assert summary.revenue == Decimal("200.00")
    assert summary.average_order_value == Decimal("200.00")
    assert summary.items_quantity == 3


async def test_payment_before_creation_does_not_poison_inbox(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    order_id, customer_id = uuid4(), uuid4()
    event = paid_event(order_id, customer_id, Decimal("100.00"), now)

    with pytest.raises(OrderNotFoundError):
        await payment_service(db_session).process(event)

    async with db_session.begin():
        processed_count = await db_session.scalar(
            select(func.count())
            .select_from(ProcessedEvent)
            .where(ProcessedEvent.event_id == event.event_id)
        )
    assert processed_count == 0

    assert await creation_service(db_session).process(created_event(order_id, customer_id, now))
    assert await payment_service(db_session).process(event)

    async with db_session.begin():
        order = await AnalyticsOrderRepository(db_session).get_by_order_id_for_update(order_id)
    assert order.paid_at is not None
