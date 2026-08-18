import asyncio

from functools import partial

from messaging_lab.consumers.order_created import handle_order_created
from messaging_lab.db.session import async_session_factory, async_engine
from messaging_lab.config import Settings

from messaging_lab.integrations.smtp import GmailSmtpNotificationProvider
from messaging_lab.messaging.rabbitmq.connection import connect_rabbitmq, create_channel
from messaging_lab.messaging.rabbitmq.topology.notifications import (
    bind_dlq,
    bind_notifications_queue,
    bind_redelivery_queue,
    bind_retry_queue,
    declare_dlq,
    declare_dlx,
    declare_notifications_queue,
    declare_order_events_exchange,
    declare_redelivery_exchange,
    declare_retry_exchange,
    declare_retry_queue,
)
from messaging_lab.services.notifications import NotificationService



async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:
        channel = await create_channel(connection)
        await channel.set_qos(prefetch_count=1)
        notifications_exchange = await declare_order_events_exchange(channel)

        dlx = await declare_dlx(channel)
        dlq = await declare_dlq(channel)

        await bind_dlq(dlx, dlq)
        

        notifications_queue = await declare_notifications_queue(channel)
        await bind_notifications_queue(notifications_exchange, notifications_queue)

        redelivery_exchange = await declare_redelivery_exchange(channel)
        await bind_redelivery_queue(redelivery_exchange, notifications_queue)

        retry_exchange = await declare_retry_exchange(channel)
        retry_queue = await declare_retry_queue(channel)
        await bind_retry_queue(retry_exchange, retry_queue)

        notification_provider = GmailSmtpNotificationProvider(
            port=settings.smtp_port,
            host=settings.smtp_host,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
            sender_email=str(settings.smtp_owner_email),
            start_tls=settings.smtp_start_tls,
            use_tls=settings.smtp_use_tls,
            timeout_seconds=settings.smtp_timeout_seconds,
        )

        notification_service = NotificationService(
            provider=notification_provider,
        )


        consumer_callback = partial(
            handle_order_created,
            retry_exchange=retry_exchange,
            notification_service=notification_service,
            session_factory=async_session_factory,
            )

        await notifications_queue.consume(consumer_callback, no_ack=False)

        await asyncio.Future()

    finally:
        await connection.close()
        await async_engine.dispose()



if __name__ == "__main__":
    asyncio.run(main())
