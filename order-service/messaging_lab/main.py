import asyncio

from messaging_lab.config import Settings
from messaging_lab.messaging.rabbitmq import (
    ORDER_CREATED_ROUTING_KEY,
    connect_rabbitmq,
    declare_events_exchange,
    create_channel,
    declare_notifications_queue,
    bind_notifications_queue,
    publish_message
)

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from messaging_lab.schemas.event import OrderCreatedV1, OrderItemV1, EventEnvelope


async def main() -> None:
    settings = Settings()
    connection = await connect_rabbitmq(url=settings.rabbitmq_url)
    try:
        channel = await create_channel(connection)
        exchange = await declare_events_exchange(channel)
        queue = await declare_notifications_queue(channel)
        await bind_notifications_queue(exchange, queue)

        print("RabbitMQ Успешно подключен")

        item = OrderItemV1(
            product_id=uuid4(),
            quantity=2,
            unit_price=Decimal("1500.00")
        )

        order_created = OrderCreatedV1(
            order_id=uuid4(),
            customer_id=uuid4(),
            items=[item],
            total_amount=Decimal("3000.00")
        )

        event = EventEnvelope[OrderCreatedV1](
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            correlation_id=uuid4(),
            payload=order_created,
        )

        print(event.model_dump_json(indent=2))
        
        await publish_message(
           exchange=exchange,
           routing_key=ORDER_CREATED_ROUTING_KEY,
           body=event.model_dump_json().encode("utf-8"),
           message_id=str(event.event_id),
           correlation_id=str(event.correlation_id)
        )

        print(f"Сообщение заказа опубликовано c ID {event.event_id}")


    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
