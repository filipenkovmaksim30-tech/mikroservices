from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from catalog_service.consumers import retry_or_send_to_dlq as retry_module


def message(headers: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        body=b"original-body",
        message_id="event-1",
        headers=headers,
        ack=AsyncMock(),
        reject=AsyncMock(),
    )


async def test_retry_republishes_before_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    incoming = message({"x-retry-count": 1})
    publish = AsyncMock()
    monkeypatch.setattr(retry_module, "publish_message", publish)

    await retry_module.retry_or_send_to_dlq(incoming, object(), "retry.route", "event-1", "order-1")

    assert publish.await_args.kwargs["body"] == b"original-body"
    assert publish.await_args.kwargs["headers"] == {"x-retry-count": 2}
    incoming.ack.assert_awaited_once()
    incoming.reject.assert_not_awaited()


@pytest.mark.parametrize("headers", [{"x-retry-count": 3}, {"x-retry-count": "bad"}])
async def test_exhausted_or_invalid_retry_goes_to_dlq(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, object]
) -> None:
    incoming = message(headers)
    publish = AsyncMock()
    monkeypatch.setattr(retry_module, "publish_message", publish)

    await retry_module.retry_or_send_to_dlq(incoming, object(), "retry.route", "event-1", "order-1")

    publish.assert_not_awaited()
    incoming.reject.assert_awaited_once_with(requeue=False)
    incoming.ack.assert_not_awaited()


async def test_failed_retry_publish_rejects_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    incoming = message()
    monkeypatch.setattr(
        retry_module, "publish_message", AsyncMock(side_effect=OSError("broker down"))
    )

    await retry_module.retry_or_send_to_dlq(incoming, object(), "retry.route", "event-1", "order-1")

    incoming.reject.assert_awaited_once_with(requeue=False)
    incoming.ack.assert_not_awaited()
