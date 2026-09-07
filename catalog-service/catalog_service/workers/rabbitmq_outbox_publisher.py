import asyncio
import logging

from catalog_service.config import Settings
from catalog_service.db.session import async_engine, async_session_factory
from catalog_service.messaging.rabbitmq.connection import connect_rabbitmq, declare_channel
from catalog_service.messaging.rabbitmq.topology.reservation_result import (
    declare_reservation_result_exchange,
)
from catalog_service.workers.rabbitmq_outbox import RabbitMQOutboxWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting outbox publisher")

    settings = Settings()

    connection = await connect_rabbitmq(settings.rabbitmq_url)
    try:
        channel = await declare_channel(connection)
        reservation_result_exchange = await declare_reservation_result_exchange(channel)
        logger.info("RabbitMQ topology declared; outbox worker is running")

        worker = RabbitMQOutboxWorker(
            session_factory=async_session_factory,
            exchange=reservation_result_exchange,
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
