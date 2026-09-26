from importlib import import_module
from unittest.mock import AsyncMock

import pytest

from messaging_lab.messaging.contracts.notifications import OrderPaidEnvelopeV1
from tests.test_order_consumers import body, incoming


@pytest.mark.parametrize("module_name", ["payment_result", "reservation_result"])
async def test_result_retry_publishes_before_ack(
    monkeypatch: pytest.MonkeyPatch, module_name: str
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    message = incoming(b"original-event")
    message.headers = {"x-retry-count": 1}
    publish = AsyncMock()
    monkeypatch.setattr(module, "publish_message", publish)

    await module.retry_or_send_to_dlq(message, object(), "retry.route", "event", "order")

    assert publish.await_args.kwargs["body"] == b"original-event"
    assert publish.await_args.kwargs["headers"] == {"x-retry-count": 2}
    message.ack.assert_awaited_once()


@pytest.mark.parametrize("module_name", ["payment_result", "reservation_result"])
@pytest.mark.parametrize("retry_count", [3, "bad", -1])
async def test_result_retry_limit_or_invalid_header_rejects(
    monkeypatch: pytest.MonkeyPatch, module_name: str, retry_count: object
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    message = incoming(b"original-event")
    message.headers = {"x-retry-count": retry_count}
    publish = AsyncMock()
    monkeypatch.setattr(module, "publish_message", publish)

    await module.retry_or_send_to_dlq(message, object(), "retry.route", "event", "order")

    publish.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.parametrize("module_name", ["payment_result", "reservation_result"])
async def test_result_retry_publish_failure_does_not_ack(
    monkeypatch: pytest.MonkeyPatch, module_name: str
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    message = incoming(b"original-event")
    monkeypatch.setattr(module, "publish_message", AsyncMock(side_effect=OSError("broker down")))

    await module.retry_or_send_to_dlq(message, object(), "retry.route", "event", "order")

    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.parametrize("retry_count", [1, 3])
async def test_notification_retry_ack_or_dlq_after_limit(
    monkeypatch: pytest.MonkeyPatch, retry_count: int
) -> None:
    module = import_module("messaging_lab.consumers.notifications")
    event = OrderPaidEnvelopeV1.model_validate_json(body("notification"))
    message = incoming(event.model_dump_json().encode())
    publish = AsyncMock()
    monkeypatch.setattr(module, "publish_message", publish)

    await module.retry_or_send_to_dlq(message, object(), event, retry_count)

    if retry_count == 1:
        assert publish.await_args.kwargs["headers"] == {"x-retry-count": 2}
        message.ack.assert_awaited_once()
    else:
        publish.assert_not_awaited()
        message.reject.assert_awaited_once_with(requeue=False)
