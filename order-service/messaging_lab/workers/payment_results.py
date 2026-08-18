import asyncio

from messaging_lab.config import Settings
from messaging_lab.messaging.rabbitmq.connection import (
    connect_rabbitmq,
    create_channel,
)
from messaging_lab.messaging.rabbitmq.topology.payment_result import (
    bind_payment_results_queue,
    declare_payment_events_exchange,
    declare_payment_results_queue,
)


async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:

        channel = await create_channel(connection)
        payment_event_exchange = await declare_payment_events_exchange(channel)
        payment_results_queue = await declare_payment_results_queue(channel)
        await bind_payment_results_queue(payment_event_exchange, payment_results_queue)

        await asyncio.Future()
    finally:
        await connection.close()



if __name__ == "__main__":
    asyncio.run(main())