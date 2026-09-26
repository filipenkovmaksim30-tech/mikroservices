import asyncio
from messaging_lab.observability import configure_logging
import logging

from messaging_lab.config import Settings
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.messaging.rabbitmq.connection import connect_rabbitmq, create_channel
from messaging_lab.messaging.rabbitmq.topology.payment_commands import (
    PAYMENT_REQUESTED_ROUTING_KEY,
    declare_payment_commands_exchange,
)
from messaging_lab.messaging.rabbitmq.topology.reservation_commands import (
    RESERVATION_REQUEST_ROUTING_KEY,
    STOCK_RESERVATION_CONFIRM_REQUESTED_ROUTING_KEY,
    STOCK_RESERVATION_RELEASE_REQUESTED_ROUTING_KEY,
    declare_reservation_exchange,
)
from messaging_lab.messaging.rabbitmq.topology.notifications import (
    declare_order_events_exchange,
    ORDER_PAID_NOTIFICATION_ROUTING_KEY,
    ORDER_FAILED_NOTIFICATION_ROUTING_KEY,
)
from messaging_lab.workers.rabbitmq_outbox import RabbitMQOutboxWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()

    logger.info("worker.starting")
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)

    try:
        channel = await create_channel(connection)
        reservation_exchange = await declare_reservation_exchange(channel)
        payment_exchange = await declare_payment_commands_exchange(channel)
        notifications_exchange = await declare_order_events_exchange(channel)

        logger.info("worker.started")

        exchanges_by_event_type={
            PAYMENT_REQUESTED_ROUTING_KEY: payment_exchange,
            RESERVATION_REQUEST_ROUTING_KEY: reservation_exchange,
            STOCK_RESERVATION_CONFIRM_REQUESTED_ROUTING_KEY: reservation_exchange,
            STOCK_RESERVATION_RELEASE_REQUESTED_ROUTING_KEY: reservation_exchange,
            ORDER_PAID_NOTIFICATION_ROUTING_KEY: notifications_exchange,
            ORDER_FAILED_NOTIFICATION_ROUTING_KEY: notifications_exchange,
        }

        worker = RabbitMQOutboxWorker(
            session_factory=async_session_factory,
            exchanges_by_event_type=exchanges_by_event_type,
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
