import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr


@pytest.mark.parametrize(
    "module_name", ["payment_results", "stock_reservation_result", "notifications"]
)
async def test_rabbit_consumer_worker_declares_topology_and_closes(
    monkeypatch: pytest.MonkeyPatch, module_name: str
) -> None:
    worker = import_module(f"messaging_lab.workers.{module_name}")
    queue = SimpleNamespace(consume=AsyncMock())
    channel = SimpleNamespace(set_qos=AsyncMock())
    connection = SimpleNamespace(close=AsyncMock())
    dispose = AsyncMock()
    declarations: dict[str, AsyncMock] = {}
    for name in dir(worker):
        if name.startswith("declare_") or name.startswith("bind_"):
            mock = AsyncMock(return_value=queue if "queue" in name or "dlq" in name else object())
            monkeypatch.setattr(worker, name, mock)
            declarations[name] = mock
    settings = SimpleNamespace(
        rabbitmq_url="amqp://test", smtp_port=587, smtp_host="smtp.test",
        smtp_username="user", smtp_password=SecretStr("password"),
        smtp_owner_email="sender@example.com", smtp_start_tls=True,
        smtp_use_tls=False, smtp_timeout_seconds=5,
    )
    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(worker, "create_channel", AsyncMock(return_value=channel))
    monkeypatch.setattr(worker, "async_engine", SimpleNamespace(dispose=dispose))
    if module_name == "notifications":
        monkeypatch.setattr(worker, "GmailSmtpNotificationProvider", lambda **_kwargs: object())

    async def cancel_wait() -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(worker.asyncio, "Future", cancel_wait)

    with pytest.raises(asyncio.CancelledError):
        await worker.main()

    channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    assert all(mock.await_count == 1 for mock in declarations.values())
    assert queue.consume.await_args.kwargs == {"no_ack": False}
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()
