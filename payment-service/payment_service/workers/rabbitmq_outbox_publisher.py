import asyncio
from payment_service.observability import configure_logging
import logging


from payment_service.config import Settings
from payment_service.db.session import async_engine, async_session_factory
from payment_service.workers.rabbitmq_outbox import RabbitMQOutboxWorker

from payment_service.messaging.rabbitmq.connection import connect_rabbitmq, declare_channel
from payment_service.messaging.rabbitmq.topology.payment_result import (
    declare_payment_events_exchange,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()
    
    logger.info("worker.starting")
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:

        channel = await declare_channel(connection)
        payment_events_exchange = await declare_payment_events_exchange(channel)
        logger.info("worker.started")

        worker = RabbitMQOutboxWorker(
            session_factory=async_session_factory,
            exchange=payment_events_exchange,
            batch_size=settings.outbox_batch_size,
            outbox_poll_interval_seconds=settings.outbox_poll_interval_seconds,
        )
        await worker.run()

    finally:
        await connection.close()
        await async_engine.dispose()
        logger.info("worker.stopped")
    





if __name__ == "__main__":
    asyncio.run(main())
