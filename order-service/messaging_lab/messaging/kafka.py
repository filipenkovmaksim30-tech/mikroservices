from aiokafka import AIOKafkaProducer
from aiokafka.structs import RecordMetadata


class KafkaEventProducer:
    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str = "order-service-outbox-publisher",
    ):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id=client_id,
            acks="all",
            enable_idempotence=True,
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, topic: str, key: bytes, value: bytes) -> RecordMetadata:
        return await self._producer.send_and_wait(topic=topic, key=key, value=value)
