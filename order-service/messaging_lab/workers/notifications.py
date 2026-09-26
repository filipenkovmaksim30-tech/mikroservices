import asyncio
from messaging_lab.observability import configure_logging

from functools import partial

from messaging_lab.consumers.notifications import handle_notification
from messaging_lab.db.session import async_session_factory, async_engine
from messaging_lab.config import Settings

from messaging_lab.integrations.smtp import GmailSmtpNotificationProvider
from messaging_lab.messaging.rabbitmq.connection import connect_rabbitmq, create_channel
from messaging_lab.messaging.rabbitmq.topology.notifications import (
    declare_order_events_exchange,
    declare_notifications_queue,
    bind_notifications_queue,
    declare_dlx,
    declare_dlq,
    bind_dlq,
    declare_retry_exchange,
    declare_retry_queue,
    bind_retry_queue,
)
from messaging_lab.services.notifications import NotificationService



async def main() -> None:
    configure_logging()
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:
        channel = await create_channel(connection)
        await channel.set_qos(prefetch_count=1)

        notifications_exchange = await declare_order_events_exchange(channel)
        notifications_queue = await declare_notifications_queue(channel)
        await bind_notifications_queue(notifications_exchange, notifications_queue)

        notifications_dlx = await declare_dlx(channel)
        notifications_dlq = await declare_dlq(channel)
        await bind_dlq(notifications_dlx, notifications_dlq)

        notification_retry_exchange = await declare_retry_exchange(channel)
        notifications_retry_queue = await declare_retry_queue(channel)
        await bind_retry_queue(notification_retry_exchange, notifications_retry_queue)

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
            handle_notification,
            retry_exchange=notification_retry_exchange,
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
