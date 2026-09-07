import asyncio
import logging
from functools import partial

from catalog_service.config import Settings
from catalog_service.consumers.reservation_commands import handle_reservation_requested
from catalog_service.db.session import async_engine, async_session_factory
from catalog_service.messaging.rabbitmq.connection import (
    connect_rabbitmq,
    declare_channel,
)
from catalog_service.messaging.rabbitmq.topology.reservation_commands import (
    bind_reservation_dlq,
    bind_reservation_queue,
    bind_reservation_retry_queue,
    declare_reservation_dlx,
    declare_reservation_exchange,
    declare_reservation_requested_dlq,
    declare_reservation_requested_queue,
    declare_reservation_retry_exchange,
    declare_reservation_retry_requested_queue,
)

logger = logging.getLogger(__name__)


RESERVATION_REQUESTED_CONSUMER = "catalog-service.stock-reservation-requested.v1"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings()
    connection = await connect_rabbitmq(settings.rabbitmq_url)

    try:
        channel = await declare_channel(connection)
        await channel.set_qos(prefetch_count=1)

        commands_exchange = await declare_reservation_exchange(channel)
        dead_letter_exchange = await declare_reservation_dlx(channel)
        retry_exchange = await declare_reservation_retry_exchange(channel)

        commands_queue = await declare_reservation_requested_queue(channel)
        await bind_reservation_queue(commands_exchange, commands_queue)

        dead_letter_queue = await declare_reservation_requested_dlq(channel)
        await bind_reservation_dlq(dead_letter_exchange, dead_letter_queue)

        retry_queue = await declare_reservation_retry_requested_queue(channel)
        await bind_reservation_retry_queue(retry_exchange, retry_queue)

        consumer_callback = partial(
            handle_reservation_requested,
            session_factory=async_session_factory,
            retry_exchange=retry_exchange,
            consumer_name=RESERVATION_REQUESTED_CONSUMER,
        )

        await commands_queue.consume(consumer_callback, no_ack=False)
        logger.info("Reservation commands consumer started")
        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
