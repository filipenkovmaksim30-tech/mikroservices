import asyncio

from functools import partial

from payment_service.db.session import async_engine, async_session_factory
from payment_service.config import Settings

from payment_service.consumers.order_payment import handle_payment_requested
from payment_service.messaging.rabbitmq.connection import connect_rabbitmq, declare_channel
from payment_service.messaging.rabbitmq.topology.payment_commands import (
    bind_payment_commands_queue,
    declare_payment_commands_exchange,
    declare_payment_commands_queue,
)

PAYMENT_REQUEST_CONSUMER = "payment-service.payment-requested.v1"

async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:
        channel = await declare_channel(connection)
        await channel.set_qos(prefetch_count=1)
        payment_exchange = await declare_payment_commands_exchange(channel)
        payment_queue = await declare_payment_commands_queue(channel)
        await bind_payment_commands_queue(payment_exchange, payment_queue)

        consumer_callback = partial(
            handle_payment_requested,
            consumer_name=PAYMENT_REQUEST_CONSUMER,
            session_factory=async_session_factory,
        )

        await payment_queue.consume(consumer_callback, no_ack=False)
        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
