import asyncio
import logging

from uuid import UUID


from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payment_service.config import Settings
from payment_service.db.session import async_engine, async_session_factory
from payment_service.services.payment_provider import PaymentProvider
from payment_service.integrations.fake_payment import FakePaymentProvider
from payment_service.repositories.payments import PaymentRepository
from payment_service.repositories.outbox import RabbitMQOutboxRepository
from payment_service.services.payment_execute import PaymentExecuteService


logger = logging.getLogger(__name__)

class PaymentExecutionWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        payment_provider: PaymentProvider,
        batch_size: int,
        poll_interval_seconds: float
        ):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        self._session_factory = session_factory
        self._payment_provider = payment_provider
        self._batch_size= batch_size
        self._poll_interval_seconds = poll_interval_seconds

    async def _get_pending_ids(self) -> list[UUID]:
        async with self._session_factory() as session:
            repository = PaymentRepository(session)
            async with session.begin():
                return await repository.get_pending_ids(limit=self._batch_size)

    async def _execute_payment(self, payment_id: UUID) -> bool:
        async with self._session_factory() as session:
            outbox_repository =  RabbitMQOutboxRepository(session)
            payment_repository = PaymentRepository(session)

            service = PaymentExecuteService(
                session=session,
                outbox_repository=outbox_repository,
                payment_repository=payment_repository,
                payment_provider=self._payment_provider,
            )
            return await service.execute(payment_id)


    async def run(self) -> None:
        while True:
            try:
                payment_ids = await self._get_pending_ids()

                for payment_id in payment_ids:
                    try:
                        await self._execute_payment(payment_id)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "Payment execution failed: payment_id=%s",
                            payment_id,
                        )

            except asyncio.CancelledError:
                logger.info("Payment execution worker cancellation requested")
                raise
            except Exception:
                logger.exception("Failed to load pending payments")

            await asyncio.sleep(self._poll_interval_seconds)


async def main() -> None:
    settings = Settings()

    try:
        payment_provider = FakePaymentProvider(
            should_succeed=settings.fake_payment_should_succeed,
            delay_seconds=settings.fake_payment_delay_seconds
        )

        worker = PaymentExecutionWorker(
            session_factory=async_session_factory,
            payment_provider=payment_provider,
            batch_size=settings.payment_execution_batch_size,
            poll_interval_seconds=settings.payment_execution_poll_interval_seconds
        )

        await worker.run()


    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())