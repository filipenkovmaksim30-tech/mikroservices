import asyncio

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition

from analytics_service.config import Settings
from analytics_service.db.session import async_engine

from analytics_service.consumers.order_events import handle_message

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
