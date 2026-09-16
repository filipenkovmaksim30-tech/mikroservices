import asyncio
import logging

from functools import partial

from catalog_service.config import Settings
from catalog_service.messaging.rabbitmq.connection import (
    connect_rabbitmq,
    declare_channel,
)
from catalog_service.messaging.rabbitmq.topology.reservation_commands import declare_reservation_exchange
from catalog_service.messaging.rabbitmq.topology.reservation_finalization import (
    declare_reservation_finalization_queue,
    bind_reservation_finalization_queue,
    declare_reservation_finalization_dlx,
    declare_reservation_finalization_dlq,
    bind_reservation_finalization_dlq,
    declare_reservation_finalization_retry_exchange,
    declare_reservation_finalization_retry_queue,
    bind_reservation_finalization_retry_queue,
)

from catalog_service.db.session import async_engine, async_session_factory
from catalog_service.consumers.reservation_finalization import handle_finalization_requested


logger = logging.getLogger(__name__)


RESERVATION_FINALIZATION_CONSUMER = "catalog-service.stock-reservation-finalization.v1"


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
        finalization_dlx = await declare_reservation_finalization_dlx(channel)
        finalization_retry_exchange = await declare_reservation_finalization_retry_exchange(channel)

        finalization_queue = await declare_reservation_finalization_queue(channel)
        await bind_reservation_finalization_queue(commands_exchange, finalization_queue)

        finalization_dlq = await declare_reservation_finalization_dlq(channel)
        await bind_reservation_finalization_dlq(finalization_dlx, finalization_dlq)

        finalization_retry_queue = await declare_reservation_finalization_retry_queue(channel)
        await bind_reservation_finalization_retry_queue(finalization_retry_exchange, finalization_retry_queue)

        logger.info("Reservation finalization topology was declared")

        consumer_callback = partial(
            handle_finalization_requested,
            session_factory=async_session_factory,
            retry_exchange=finalization_retry_exchange,
            consumer_name=RESERVATION_FINALIZATION_CONSUMER,
        )
        
        await finalization_queue.consume(consumer_callback, no_ack=False)
        logger.info("Reservation commands consumer started")
        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
