from typing import Protocol


from messaging_lab.schemas.event import EventEnvelope, OrderCreatedV1


class TransientNotificationError(Exception):
    pass


class PermanentNotificationError(Exception):
    pass


class NotificationProvider(Protocol):
    async def send_order_created(
        self,
        event: EventEnvelope[OrderCreatedV1],
        idempotency_key: str,
    ) -> None:
        ...


class ConsoleNotificationProvider:
    async def send_order_created(
        self,
        event: EventEnvelope[OrderCreatedV1],
        idempotency_key: str,
    ) -> None:
        print(
            "Notification processed:",
            f"order_id={event.payload.order_id}",
            f"receipt_email={event.payload.receipt_email}",
            f"event_id={event.event_id}",
            f"idempotency_key={idempotency_key}",
        )


class NotificationService:
    def __init__(self, provider: NotificationProvider) -> None:
        self._provider = provider

    async def process_order_created(
        self,
        event: EventEnvelope[OrderCreatedV1],
    ) -> None:
        await self._provider.send_order_created(
            event=event,
            idempotency_key=str(event.event_id),
        )
