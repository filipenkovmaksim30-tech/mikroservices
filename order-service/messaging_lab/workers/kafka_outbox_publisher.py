import asyncio
from messaging_lab.observability import configure_logging
import logging

from messaging_lab.config import Settings
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.messaging.kafka import KafkaEventProducer
from messaging_lab.workers.kafka_outbox import KafkaOutboxWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()

    settings = Settings()
    kafka_producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    producer_started = False

    logger.info("worker.starting")

    try:
        await kafka_producer.start()
        producer_started = True
        logger.info("worker.started")

        worker = KafkaOutboxWorker(
            session_factory=async_session_factory,
            kafka_producer=kafka_producer,
            topic=settings.kafka_analytics_topic,
            batch_size=settings.outbox_batch_size,
            outbox_poll_interval_seconds=settings.outbox_poll_interval_seconds,
        )
        await worker.run()

    finally:
        if producer_started:
            await kafka_producer.stop()
        await async_engine.dispose()
        logger.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
