import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize(
    ("module_name", "consumer_name"),
    [
        ("reservation_commands", "catalog-service.stock-reservation-requested.v1"),
        ("reservation_finalization", "catalog-service.stock-reservation-finalization.v1"),
    ],
)
async def test_consumer_worker_declares_topology_and_closes_on_cancel(
    monkeypatch: pytest.MonkeyPatch, module_name: str, consumer_name: str
) -> None:
    worker = import_module(f"catalog_service.workers.{module_name}")
    queue = SimpleNamespace(consume=AsyncMock())
    exchange = object()
    channel = SimpleNamespace(set_qos=AsyncMock())
    connection = SimpleNamespace(close=AsyncMock())
    dispose = AsyncMock()
    declarations: dict[str, AsyncMock] = {}

    for name in dir(worker):
        if name != "declare_channel" and (
            name.startswith("declare_") or name.startswith("bind_")
        ):
            result = queue if "queue" in name else exchange
            mock = AsyncMock(return_value=result)
            monkeypatch.setattr(worker, name, mock)
            declarations[name] = mock

    monkeypatch.setattr(worker, "Settings", lambda: SimpleNamespace(rabbitmq_url="amqp://test"))
    monkeypatch.setattr(worker, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(worker, "declare_channel", AsyncMock(return_value=channel))
    monkeypatch.setattr(worker, "async_engine", SimpleNamespace(dispose=dispose))

    async def cancel_wait() -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(worker.asyncio, "Future", cancel_wait)

    with pytest.raises(asyncio.CancelledError):
        await worker.main()

    channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    assert all(mock.await_count == 1 for mock in declarations.values())
    callback = queue.consume.await_args.args[0]
    assert callback.keywords["consumer_name"] == consumer_name
    assert queue.consume.await_args.kwargs == {"no_ack": False}
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()
