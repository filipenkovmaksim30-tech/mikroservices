import asyncio
from functools import partial

from messaging_lab.config import Settings
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.messaging.rabbitmq.connection import connect_rabbitmq, create_channel
from messaging_lab.messaging.rabbitmq.topology.reservation_result import (
    bind_reservation_result_dlq,
    bind_reservation_result_queue,
    bind_reservation_results_retry_queue,
    declare_reservation_result_dlq,
    declare_reservation_result_dlx,
    declare_reservation_result_exchange,
    declare_reservation_result_queue,
    declare_reservation_results_retry_exchange,
    declare_reservation_results_retry_queue,
)
from messaging_lab.consumers.reservation_result import handler_stock_reservation_result

STOCK_RESERVATION_RESULTS_CONSUMER = "order-service.stock-reservation-results.v1"

async def main() -> None:
    settings = Settings()

    connection = await connect_rabbitmq(settings.rabbitmq_url)

    try:
        channel = await create_channel(connection)
        await channel.set_qos(prefetch_count=1)

        stock_reservation_exchange = await declare_reservation_result_exchange(channel)
        stock_reservation_queue = await declare_reservation_result_queue(channel)
        await bind_reservation_result_queue(stock_reservation_exchange, stock_reservation_queue)

        stock_reservation_dlx = await declare_reservation_result_dlx(channel)
        stock_reservation_dlq = await declare_reservation_result_dlq(channel)
        await bind_reservation_result_dlq(stock_reservation_dlx, stock_reservation_dlq)


        stock_reservation_retry_exchange = await declare_reservation_results_retry_exchange(channel)
        stock_reservation_retry_queue = await declare_reservation_results_retry_queue(channel)
        await bind_reservation_results_retry_queue(stock_reservation_retry_exchange, stock_reservation_retry_queue)

        consumer_callback = partial(
            handler_stock_reservation_result,
            retry_exchange=stock_reservation_retry_exchange,
            consumer_name=STOCK_RESERVATION_RESULTS_CONSUMER,
            session_factory=async_session_factory,
        )

        await stock_reservation_queue.consume(consumer_callback, no_ack=False)
        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
