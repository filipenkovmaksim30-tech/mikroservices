import logging
from typing import Protocol

from messaging_lab.messaging.contracts.notifications import OrderNotificationEnvelopeV1

logger = logging.getLogger(__name__)

class TransientNotificationError(Exception):
    pass


class PermanentNotificationError(Exception):
    pass


class NotificationProvider(Protocol):
    async def send_order_notifications(
        self,
        event: OrderNotificationEnvelopeV1,
        idempotency_key: str,
    ) -> None:
        ...


class ConsoleNotificationProvider:
    async def send_order_notifications(
        self,
        event: OrderNotificationEnvelopeV1,
        idempotency_key: str,
    ) -> None:
        logger.info(
            "notification.console_processed",
            extra={
                "event_type": event.event_type,
                "event_id": event.event_id,
                "order_id": event.payload.order_id,
            },
        )

class NotificationService:
    def __init__(self, provider: NotificationProvider) -> None:
        self._provider = provider

    async def process_notification(
        self,
        event: OrderNotificationEnvelopeV1,
    ) -> None:
        await self._provider.send_order_notifications(
            event=event,
            idempotency_key=str(event.event_id),
        )
