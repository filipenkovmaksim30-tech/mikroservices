import os
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from messaging_lab.db.models import (
    Base,
    InboxEvent,
    KafkaOutboxEvent,
    Order,
    OrderItem,
    OrderStatus,
    RabbitMQOutboxEvent,
)
from messaging_lab.messaging.contracts.payments import PaymentSucceededEnvelope, PaymentSucceededV1
from messaging_lab.messaging.contracts.stock_reservations import (
    StockReservedEnvelopeV1,
    StockReservedV1,
)
from messaging_lab.repositories.inbox import InboxRepository
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.schemas.catalog import CatalogProductSnapshot
from messaging_lab.services.orders import CreateOrderItem, OrderService
from messaging_lab.services.payment_result import PaymentResultService
from messaging_lab.services.reservation_result import StockReservationResultService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    raw_url = os.environ.get("ORDER_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("Set ORDER_TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("ORDER_TEST_DATABASE_URL must point to a dedicated PostgreSQL *_test DB")

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


async def test_creation_and_redelivery_write_one_order_and_outboxes(
    db_session: AsyncSession,
) -> None:
    product_id = uuid4()
    customer_id = uuid4()
    catalog = SimpleNamespace(
        get_products_by_ids=AsyncMock(
            return_value=[
                CatalogProductSnapshot(
                    id=product_id,
                    price=Decimal("125.50"),
                    stock_quantity=10,
                    is_active=True,
                )
            ]
        )
    )
    service = OrderService(
        session=db_session,
        order_repository=OrderRepository(db_session),
        catalog_client=catalog,
        rabbitmq_outbox_repository=RabbitMQOutboxRepository(db_session),
        kafka_outbox_repository=KafkaOutboxRepository(db_session),
    )
    items = [CreateOrderItem(product_id=product_id, quantity=2)]

    first = await service.create_order(customer_id, "buyer@example.com", "key-1", items)
    repeated = await service.create_order(customer_id, "buyer@example.com", "key-1", items)

    async with db_session.begin():
        order_count = await db_session.scalar(
            select(func.count()).select_from(Order).where(Order.id == first.id)
        )
        stored_item = await db_session.scalar(
            select(OrderItem).where(OrderItem.order_id == first.id)
        )
        rabbit_count = await db_session.scalar(
            select(func.count())
            .select_from(RabbitMQOutboxEvent)
            .where(RabbitMQOutboxEvent.aggregate_id == first.id)
        )
        kafka_count = await db_session.scalar(
            select(func.count())
            .select_from(KafkaOutboxEvent)
            .where(KafkaOutboxEvent.aggregate_id == first.id)
        )

    assert repeated.id == first.id
    assert catalog.get_products_by_ids.await_count == 1
    assert order_count == 1
    assert first.status is OrderStatus.PENDING_STOCK
    assert first.total_amount == Decimal("251.00")
    assert stored_item is not None
    assert stored_item.unit_price == Decimal("125.50")
    assert rabbit_count == 1
    assert kafka_count == 1


async def test_reservation_then_payment_updates_order_with_inbox_and_outboxes(
    db_session: AsyncSession,
) -> None:
    order = Order(
        customer_id=uuid4(),
        receipt_email="buyer@example.com",
        total_amount=Decimal("100.00"),
        status=OrderStatus.PENDING_STOCK,
        items=[],
    )
    async with db_session.begin():
        await OrderRepository(db_session).add(order)

    reserved_at = datetime.now(UTC)
    reservation_event = StockReservedEnvelopeV1(
        event_id=uuid4(),
        occurred_at=reserved_at,
        correlation_id=order.id,
        payload=StockReservedV1(
            reservation_id=uuid4(), order_id=order.id, reserved_at=reserved_at
        ),
    )
    reservation_service = StockReservationResultService(
        session=db_session,
        inbox_repository=InboxRepository(db_session),
        order_repository=OrderRepository(db_session),
        outbox_repository=RabbitMQOutboxRepository(db_session),
        consumer_name="reservation-results-test",
    )

    assert await reservation_service.process(reservation_event) is True

    payment_event = PaymentSucceededEnvelope(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order.id,
        payload=PaymentSucceededV1(
            payment_id=uuid4(),
            order_id=order.id,
            amount=order.total_amount,
            currency="RUB",
            completed_at=datetime.now(UTC),
        ),
    )
    payment_service = PaymentResultService(
        session=db_session,
        inbox_repository=InboxRepository(db_session),
        outbox_repository=RabbitMQOutboxRepository(db_session),
        kafka_outbox_repository=KafkaOutboxRepository(db_session),
        order_repository=OrderRepository(db_session),
        consumer_name="payment-results-test",
    )

    assert await payment_service.process(payment_event) is True

    async with db_session.begin():
        stored_order = await OrderRepository(db_session).get_by_id(order.id)
        inbox_count = await db_session.scalar(
            select(func.count())
            .select_from(InboxEvent)
            .where(InboxEvent.event_id.in_([reservation_event.event_id, payment_event.event_id]))
        )
        rabbit_types = (
            await db_session.scalars(
                select(RabbitMQOutboxEvent.event_type).where(
                    RabbitMQOutboxEvent.aggregate_id == order.id
                )
            )
        ).all()
        kafka_types = (
            await db_session.scalars(
                select(KafkaOutboxEvent.event_type).where(KafkaOutboxEvent.aggregate_id == order.id)
            )
        ).all()

    assert stored_order is not None
    assert stored_order.status is OrderStatus.PAID
    assert inbox_count == 2
    assert set(rabbit_types) == {
        "payment.requested", "stock.reservation.confirm.requested", "order.paid"
    }
    assert kafka_types == ["order.paid"]
