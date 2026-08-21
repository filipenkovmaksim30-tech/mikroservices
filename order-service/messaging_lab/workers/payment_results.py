import asyncio
from functools import partial

from messaging_lab.config import Settings
from messaging_lab.messaging.rabbitmq.connection import (
    connect_rabbitmq,
    create_channel,
)
from messaging_lab.db.session import async_engine, async_session_factory
from messaging_lab.consumers.payment_result import handler_payment_result
from messaging_lab.messaging.rabbitmq.topology.payment_result import (
    bind_payment_results_queue,
    declare_payment_events_exchange,
    declare_payment_results_queue,
    declare_payment_results_dlx,
    declare_payment_results_dlq,
    bind_payment_results_dlq,
    declare_payment_results_retry_exchange,
    declare_payment_results_retry_queue,
    bind_payment_results_retry_queue,
)

PAYMENT_RESULTS_CONSUMER = "order-service.payment-results.v1"


async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:

        channel = await create_channel(connection)
        await channel.set_qos(prefetch_count=1)
        payment_event_exchange = await declare_payment_events_exchange(channel)
        payment_results_queue = await declare_payment_results_queue(channel)
        await bind_payment_results_queue(payment_event_exchange, payment_results_queue)

        payment_results_dlx = await declare_payment_results_dlx(channel)
        payment_results_dlq = await declare_payment_results_dlq(channel)
        await bind_payment_results_dlq(payment_results_dlx, payment_results_dlq)

        payment_results_retry_exchange = await declare_payment_results_retry_exchange(channel)
        payment_results_retry_queue = await declare_payment_results_retry_queue(channel)
        await bind_payment_results_retry_queue(payment_results_retry_exchange, payment_results_retry_queue)

        consumer_callback = partial(
            handler_payment_result,
            retry_exchange=payment_results_retry_exchange,
            consumer_name=PAYMENT_RESULTS_CONSUMER,
            session_factory=async_session_factory,
        )

        await payment_results_queue.consume(consumer_callback, no_ack=False)

        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()



if __name__ == "__main__":
    asyncio.run(main())