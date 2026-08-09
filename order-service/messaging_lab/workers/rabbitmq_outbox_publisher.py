import asyncio
import logging

from messaging_lab.config import Settings
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.messaging.rabbitmq import (
    connect_rabbitmq,
    create_channel,
    declare_payments_exchange,
)
from messaging_lab.workers.rabbitmq_outbox import RabbitMQOutboxWorker


logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("Starting outbox publisher")
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)

    try:
        channel = await create_channel(connection)
        exchange = await declare_payments_exchange(channel)
        logger.info("RabbitMQ topology declared; outbox worker is running")

        worker = RabbitMQOutboxWorker(
            session_factory=async_session_factory,
            exchange=exchange,
            batch_size=settings.outbox_batch_size,
            outbox_poll_interval_seconds=settings.outbox_poll_interval_seconds,
        )
        await worker.run()
    finally:
        await connection.close()
        await async_engine.dispose()
        logger.info("Outbox publisher stopped")


if __name__ == "__main__":
    asyncio.run(main())
