import asyncio
from aio_pika.abc import AbstractIncomingMessage
from payment_service.db.session import async_engine
from payment_service.config import Settings

from payment_service.consumers.order_payment import handle_payment_requested
from payment_service.messaging.rabbitmq import (
    connect_rabbitmq,
    declare_channel,
    declare_payments_exchange, 
    declare_payments_queue,
    bind_payments_queue
)



async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:
        channel = await declare_channel(connection)
        await channel.set_qos(prefetch_count=1)
        payment_exchange = await declare_payments_exchange(channel)
        payment_queue = await declare_payments_queue(channel)
        await bind_payments_queue(payment_exchange, payment_queue)

        await payment_queue.consume(handle_payment_requested, no_ack=False)
        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
