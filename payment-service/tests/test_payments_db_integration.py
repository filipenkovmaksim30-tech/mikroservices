import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from payment_service.db.models import Base, InboxEvent, Payment, PaymentStatus, RabbitMQOutboxEvent
from payment_service.integrations.fake_payment import FakePaymentProvider
from payment_service.messaging.contracts import PaymentRequestedEnvelope, PaymentRequestedV1
from payment_service.repositories.inbox import InboxRepository
from payment_service.repositories.outbox import RabbitMQOutboxRepository
from payment_service.repositories.payments import PaymentRepository
from payment_service.services.payment_execute import PaymentExecuteService
from payment_service.services.payment_processing import PaymentProcessingService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    raw_url = os.environ.get("PAYMENT_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("Set PAYMENT_TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("PAYMENT_TEST_DATABASE_URL must point to a dedicated PostgreSQL *_test DB")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        # Only the explicitly supplied test database is modified. No existing data is deleted.
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


async def test_redelivery_does_not_insert_second_payment(db_session: AsyncSession) -> None:
    order_id = uuid4()
    event = PaymentRequestedEnvelope(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=order_id,
        payload=PaymentRequestedV1(
            order_id=order_id, amount=Decimal("100.00"), currency="RUB"
        ),
    )
    service = PaymentProcessingService(
        session=db_session,
        payment_repository=PaymentRepository(db_session),
        inbox_repository=InboxRepository(db_session),
        consumer_name="payment-commands-test",
    )

    assert await service.process(event) is True
    assert await service.process(event) is False

    async with db_session.begin():
        payments_count = await db_session.scalar(
            select(func.count()).select_from(Payment).where(Payment.order_id == order_id)
        )
        inbox_count = await db_session.scalar(
            select(func.count())
            .select_from(InboxEvent)
            .where(InboxEvent.event_id == event.event_id)
        )

    assert payments_count == 1
    assert inbox_count == 1


async def test_successful_execution_commits_payment_and_outbox(
    db_session: AsyncSession,
) -> None:
    payment = Payment(
        order_id=uuid4(),
        amount=Decimal("100.00"),
        currency="RUB",
        status=PaymentStatus.PENDING,
    )
    async with db_session.begin():
        await PaymentRepository(db_session).add(payment)

    service = PaymentExecuteService(
        session=db_session,
        outbox_repository=RabbitMQOutboxRepository(db_session),
        payment_repository=PaymentRepository(db_session),
        payment_provider=FakePaymentProvider(should_succeed=True, delay_seconds=0),
        payment_processing_lease_seconds=30,
    )

    assert await service.execute(payment.id) is True

    async with db_session.begin():
        stored = await PaymentRepository(db_session).get_by_id(payment.id)
        events = (
            await db_session.scalars(
                select(RabbitMQOutboxEvent).where(
                    RabbitMQOutboxEvent.aggregate_id == payment.id
                )
            )
        ).all()

    assert stored is not None
    assert stored.status is PaymentStatus.SUCCEEDED
    assert stored.completed_at is not None
    assert len(events) == 1
    assert events[0].event_type == "payment.succeeded"
    assert events[0].payload["order_id"] == str(payment.order_id)
