from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiokafka import TopicPartition


class OneRecordConsumer:
    def __init__(self, record: object) -> None:
        self.record = record
        self.commit = AsyncMock()

    async def __aiter__(self):
        yield self.record


def worker_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "unused-test-key.pem")
    return import_module("analytics_service.workers.kafka_consumer")


async def test_offset_committed_only_after_successful_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = worker_module(monkeypatch)
    record = SimpleNamespace(topic="orders.analytics.v1", partition=2, offset=17)
    consumer = OneRecordConsumer(record)
    handler = AsyncMock()
    monkeypatch.setattr(worker, "handle_message", handler)

    await worker.consume_messages(consumer, object(), object())

    handler.assert_awaited_once()
    consumer.commit.assert_awaited_once_with({TopicPartition(record.topic, 2): 18})


async def test_handler_failure_does_not_commit_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = worker_module(monkeypatch)
    consumer = OneRecordConsumer(
        SimpleNamespace(topic="orders.analytics.v1", partition=0, offset=1)
    )
    monkeypatch.setattr(worker, "handle_message", AsyncMock(side_effect=RuntimeError("DB down")))

    with pytest.raises(RuntimeError, match="DB down"):
        await worker.consume_messages(consumer, object(), object())

    consumer.commit.assert_not_awaited()


async def test_dlq_preserves_payload_and_origin_headers() -> None:
    publish_to_dlq = import_module("analytics_service.messaging.kafka_dlq").publish_to_dlq
    producer = SimpleNamespace(send_and_wait=AsyncMock())
    message = SimpleNamespace(
        topic="orders.analytics.v1",
        partition=1,
        offset=42,
        key=b"order-id",
        value=b"bad-json",
        headers=[("trace-id", b"trace")],
    )

    await publish_to_dlq(producer, "orders.analytics.dlq.v1", message, "validation_error")

    kwargs = producer.send_and_wait.await_args.kwargs
    assert kwargs["topic"] == "orders.analytics.dlq.v1"
    assert kwargs["key"] == b"order-id"
    assert kwargs["value"] == b"bad-json"
    assert dict(kwargs["headers"]) == {
        "trace-id": b"trace",
        "x-error-type": b"validation_error",
        "x-original-topic": b"orders.analytics.v1",
        "x-original-partition": b"1",
        "x-original-offset": b"42",
    }


@pytest.mark.parametrize("fail_consume", [False, True])
async def test_worker_stops_clients_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch, fail_consume: bool
) -> None:
    worker = worker_module(monkeypatch)
    producer = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    consumer = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    dispose = AsyncMock()
    consume = AsyncMock(side_effect=RuntimeError("processing failed") if fail_consume else None)
    monkeypatch.setattr(worker, "Settings", lambda: SimpleNamespace(
        kafka_bootstrap_servers="kafka.test:9092",
        kafka_analytics_topic="orders.analytics.v1",
        kafka_consumer_group="analytics-test",
    ))
    monkeypatch.setattr(worker, "AIOKafkaProducer", lambda **_kwargs: producer)
    monkeypatch.setattr(worker, "AIOKafkaConsumer", lambda *_args, **_kwargs: consumer)
    monkeypatch.setattr(worker, "consume_messages", consume)
    monkeypatch.setattr(worker, "async_engine", SimpleNamespace(dispose=dispose))

    if fail_consume:
        with pytest.raises(RuntimeError, match="processing failed"):
            await worker.run()
    else:
        await worker.run()

    producer.start.assert_awaited_once()
    consumer.start.assert_awaited_once()
    consumer.stop.assert_awaited_once()
    producer.stop.assert_awaited_once()
    dispose.assert_awaited_once()
