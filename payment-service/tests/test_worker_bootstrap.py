import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


async def test_payment_command_worker_declares_topology_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("payment_service.workers.payment_handler")
    queue = SimpleNamespace(consume=AsyncMock())
    exchange = object()
    channel = SimpleNamespace(set_qos=AsyncMock())
    connection = SimpleNamespace(close=AsyncMock())
    dispose = AsyncMock()
    declarations: dict[str, AsyncMock] = {}
    for name in dir(module):
        if name != "declare_channel" and (name.startswith("declare_") or name.startswith("bind_")):
            mock = AsyncMock(return_value=queue if "queue" in name else exchange)
            monkeypatch.setattr(module, name, mock)
            declarations[name] = mock
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(rabbitmq_url="amqp://test"))
    monkeypatch.setattr(module, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(module, "declare_channel", AsyncMock(return_value=channel))
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))

    async def cancel_wait() -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(module.asyncio, "Future", cancel_wait)

    with pytest.raises(asyncio.CancelledError):
        await module.main()

    channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    assert all(mock.await_count == 1 for mock in declarations.values())
    callback = queue.consume.await_args.args[0]
    assert callback.keywords["consumer_name"] == module.PAYMENT_REQUEST_CONSUMER
    assert queue.consume.await_args.kwargs == {"no_ack": False}
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()


async def test_payment_outbox_worker_closes_connection_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("payment_service.workers.rabbitmq_outbox_publisher")
    connection = SimpleNamespace(close=AsyncMock())
    dispose = AsyncMock()
    run = AsyncMock(side_effect=RuntimeError("batch failed"))
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(
        rabbitmq_url="amqp://test", outbox_batch_size=10,
        outbox_poll_interval_seconds=1,
    ))
    monkeypatch.setattr(module, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(module, "declare_channel", AsyncMock(return_value=object()))
    monkeypatch.setattr(module, "declare_payment_events_exchange", AsyncMock(return_value=object()))
    monkeypatch.setattr(module, "RabbitMQOutboxWorker", lambda **_kwargs: SimpleNamespace(run=run))
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))

    with pytest.raises(RuntimeError, match="batch failed"):
        await module.main()

    run.assert_awaited_once()
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()
