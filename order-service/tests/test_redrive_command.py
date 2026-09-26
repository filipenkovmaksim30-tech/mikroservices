from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from messaging_lab.services.payment_result_redrive import RedriveDecision, RedriveStatus
from tests.test_payment_result_redrive import result_event


def redrive_module():
    return import_module("messaging_lab.tools.payment_result_redrive")


@pytest.mark.parametrize(
    ("execute", "decision", "should_publish"),
    [
        (False, RedriveStatus.READY, False),
        (True, RedriveStatus.CONFLICT, False),
        (True, RedriveStatus.READY, True),
    ],
)
async def test_redrive_command_only_publishes_after_explicit_ready_inspection(
    monkeypatch: pytest.MonkeyPatch,
    execute: bool,
    decision: RedriveStatus,
    should_publish: bool,
) -> None:
    module = redrive_module()
    event = result_event(succeeded=True)
    message = SimpleNamespace(
        body=event.model_dump_json().encode(), message_id="event-1",
        ack=AsyncMock(), nack=AsyncMock(), processed=False,
    )
    queue = SimpleNamespace(get=AsyncMock(return_value=message))
    exchange = object()
    channel = SimpleNamespace(
        get_exchange=AsyncMock(return_value=exchange),
        get_queue=AsyncMock(return_value=queue),
    )
    connection = SimpleNamespace(close=AsyncMock())
    session = AsyncMock()
    session.__aenter__.return_value = object()
    publish = AsyncMock()
    dispose = AsyncMock()
    monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(rabbitmq_url="amqp://test"))
    monkeypatch.setattr(module, "connect_rabbitmq", AsyncMock(return_value=connection))
    monkeypatch.setattr(module, "create_channel", AsyncMock(return_value=channel))
    monkeypatch.setattr(module, "async_session_factory", Mock(return_value=session))
    monkeypatch.setattr(module, "async_engine", SimpleNamespace(dispose=dispose))
    monkeypatch.setattr(module, "publish_message", publish)
    inspect = AsyncMock(return_value=RedriveDecision(decision, "test decision"))
    monkeypatch.setattr(
        module, "PaymentResultRedriveService", lambda **_kwargs: SimpleNamespace(inspect=inspect)
    )

    await module.run_payment_result_redrive(
        execute=execute, expected_event_id=event.event_id if execute else None
    )

    inspect.assert_awaited_once()
    if should_publish:
        assert publish.await_args.kwargs["headers"] == {"x-retry-count": 0}
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()
    else:
        publish.assert_not_awaited()
        message.nack.assert_awaited_once_with(requeue=True)
        message.ack.assert_not_awaited()
    connection.close.assert_awaited_once()
    dispose.assert_awaited_once()


async def test_redrive_publish_failure_returns_message_to_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = redrive_module()
    event = result_event(succeeded=True)
    message = SimpleNamespace(body=event.model_dump_json().encode(), ack=AsyncMock())
    monkeypatch.setattr(
        module, "publish_message", AsyncMock(side_effect=OSError("broker down"))
    )

    with pytest.raises(OSError, match="broker down"):
        await module.redrive_message(message, event, object())

    message.ack.assert_not_awaited()
