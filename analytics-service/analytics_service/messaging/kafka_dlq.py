from aiokafka import AIOKafkaProducer, ConsumerRecord


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