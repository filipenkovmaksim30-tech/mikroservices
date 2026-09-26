import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from messaging_lab.workers import kafka_outbox, rabbitmq_outbox


@pytest.mark.parametrize("kind", ["rabbitmq", "kafka"])
@pytest.mark.parametrize("publish_fails", [False, True])
async def test_outbox_worker_polls_or_retries_after_batch(
    monkeypatch: pytest.MonkeyPatch, kind: str, publish_fails: bool
) -> None:
    module = rabbitmq_outbox if kind == "rabbitmq" else kafka_outbox
    publisher_name = "RabbitMQOutboxPublisher" if kind == "rabbitmq" else "KafkaOutboxPublisher"
    publish = AsyncMock(side_effect=OSError("broker down") if publish_fails else None)
    publish.return_value = 0
    monkeypatch.setattr(
        module, publisher_name, lambda **_kwargs: SimpleNamespace(publish_batch=publish)
    )
    session = AsyncMock()
    session.__aenter__.return_value = object()
    factory = Mock(return_value=session)
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(
        module, "asyncio", SimpleNamespace(CancelledError=asyncio.CancelledError, sleep=sleep)
    )
    if kind == "rabbitmq":
        worker = module.RabbitMQOutboxWorker(factory, {}, 10, 0.1)
    else:
        worker = module.KafkaOutboxWorker(factory, object(), "analytics", 10, 0.1)

    with pytest.raises(asyncio.CancelledError):
        await worker.run()

    publish.assert_awaited_once()
    sleep.assert_awaited_once_with(0.1)


async def test_rabbitmq_publisher_main_closes_connection_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("messaging_lab.workers.rabbitmq_outbox_publisher")
    connection = SimpleNamespace(close=AsyncMock())
    dispose = AsyncMock()
    run = AsyncMock(side_effect=RuntimeError("batch failed"))
    exchanges = {}
    for name in (
        "declare_reservation_exchange", "declare_payment_commands_exchange",
        "declare_order_events_exchange",
    ):
        monkeypatch.setattr(module, name, AsyncMock(return_value=object()))
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(
        rabbitmq_url="amqp://test", outbox_batch_size=10,
        outbox_poll_interval_seconds=0.1,
    ))
    monkeypatch.setattr(module, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(module, "create_channel", AsyncMock(return_value=object()))
    monkeypatch.setattr(module, "RabbitMQOutboxWorker", lambda **kwargs: (
        exchanges.update(kwargs["exchanges_by_event_type"]) or SimpleNamespace(run=run)
    ))
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(RuntimeError, match="batch failed"):
        await module.main()

    assert set(exchanges) == {
        "payment.requested", "stock.reservation.requested",
        "stock.reservation.confirm.requested", "stock.reservation.release.requested",
        "order.paid", "order.payment_failed",
    }
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()


async def test_kafka_publisher_main_stops_producer_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("messaging_lab.workers.kafka_outbox_publisher")
    producer = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    run = AsyncMock(side_effect=RuntimeError("batch failed"))
    dispose = AsyncMock()
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(
        kafka_bootstrap_servers="kafka.test:9092", kafka_analytics_topic="analytics",
        outbox_batch_size=10, outbox_poll_interval_seconds=0.1,
    ))
    monkeypatch.setattr(module, "KafkaEventProducer", lambda _servers: producer)
    monkeypatch.setattr(module, "KafkaOutboxWorker", lambda **_kwargs: SimpleNamespace(run=run))
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(RuntimeError, match="batch failed"):
        await module.main()

    producer.start.assert_awaited_once()
    producer.stop.assert_awaited_once()
    dispose.assert_awaited_once()
