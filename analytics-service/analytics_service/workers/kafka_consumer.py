import asyncio

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from aiokafka.structs import ConsumerRecord
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from analytics_service.config import Settings
from analytics_service.db.session import async_engine, async_session_factory
from analytics_service.messaging.contract import (
    AnalyticsEventEnvelope,
    OrderCreatedAnalyticsV1,
)
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.repositories.processed_event import ProcessedEventRepository
from analytics_service.services.order_created import OrderCreatedAnalyticsService


async def process_message(
    message: ConsumerRecord,
    session_factory: async_sessionmaker[AsyncSession],
    consumer_name: str,
) -> bool:
    event = AnalyticsEventEnvelope[OrderCreatedAnalyticsV1].model_validate_json(message.value)

    async with session_factory() as session:
        analytics_order_repository = AnalyticsOrderRepository(session)
        processed_event_repository = ProcessedEventRepository(session)

        analytics_service = OrderCreatedAnalyticsService(
            session=session,
            analytics_order_repository=analytics_order_repository,
            processed_event_repository=processed_event_repository,
            consumer_name=consumer_name,
        )

        return await analytics_service.process(event)


async def publish_to_dlq(
    producer: AIOKafkaProducer,
    dlq_topic: str,
    message: ConsumerRecord,
) -> None:
    headers = list(message.headers or [])
    headers.extend(
        [
            ("x-error-type", b"validation_error"),
            ("x-original-topic", message.topic.encode("utf-8")),
            (
                "x-original-partition",
                str(message.partition).encode("utf-8"),
            ),
            ("x-original-offset", str(message.offset).encode("utf-8")),
        ]
    )

    await producer.send_and_wait(
        topic=dlq_topic,
        key=message.key,
        value=message.value,
        headers=headers,
    )


async def handle_message(
    message: ConsumerRecord,
    dlq_producer: AIOKafkaProducer,
    settings: Settings,
) -> None:
    try:
        await process_message(
            message=message,
            session_factory=async_session_factory,
            consumer_name=settings.kafka_consumer_group,
        )
    except ValidationError:
        await publish_to_dlq(
            producer=dlq_producer,
            dlq_topic=settings.kafka_analytics_dlq_topic,
            message=message,
        )


async def consume_messages(
    consumer: AIOKafkaConsumer,
    dlq_producer: AIOKafkaProducer,
    settings: Settings,
) -> None:
    async for message in consumer:
        await handle_message(
            message=message,
            dlq_producer=dlq_producer,
            settings=settings,
        )

        topic_partition = TopicPartition(
            message.topic,
            message.partition,
        )
        await consumer.commit(
            {
                topic_partition: message.offset + 1,
            }
        )


async def run() -> None:
    settings = Settings()

    dlq_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id="analytics-service-dlq-producer",
        acks="all",
        enable_idempotence=True,
    )
    kafka_consumer = AIOKafkaConsumer(
        settings.kafka_analytics_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )

    consumer_started = False
    producer_started = False

    try:
        await dlq_producer.start()
        producer_started = True

        await kafka_consumer.start()
        consumer_started = True

        await consume_messages(
            consumer=kafka_consumer,
            dlq_producer=dlq_producer,
            settings=settings,
        )
    finally:
        if consumer_started:
            await kafka_consumer.stop()

        if producer_started:
            await dlq_producer.stop()

        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
