from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from analytics_service.exceptions import AnalyticsOrderDataMismatchError


def handler_module(monkeypatch: pytest.MonkeyPatch):
    # The local analytics .env lacks this required setting; no key is read by these tests.
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "unused-test-key.pem")
    return import_module("analytics_service.consumers.order_events")


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        kafka_consumer_group="analytics-test",
        kafka_analytics_dlq_topic="analytics-test-dlq",
    )


async def test_invalid_json_is_sent_to_dlq(monkeypatch: pytest.MonkeyPatch) -> None:
    module = handler_module(monkeypatch)
    publish_to_dlq = AsyncMock()
    monkeypatch.setattr(module, "publish_to_dlq", publish_to_dlq)
    record = SimpleNamespace(value=b"not JSON")
    producer = object()

    await module.handle_message(record, producer, settings())

    publish_to_dlq.assert_awaited_once_with(
        producer=producer,
        dlq_topic="analytics-test-dlq",
        message=record,
        error_type="validation_error",
    )


async def test_permanent_business_conflict_is_sent_to_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = handler_module(monkeypatch)
    publish_to_dlq = AsyncMock()
    monkeypatch.setattr(module, "publish_to_dlq", publish_to_dlq)
    monkeypatch.setattr(
        module,
        "process_message",
        AsyncMock(side_effect=AnalyticsOrderDataMismatchError(uuid4(), "customer_id")),
    )

    await module.handle_message(object(), object(), settings())

    assert publish_to_dlq.await_args.kwargs["error_type"] == "AnalyticsOrderDataMismatchError"


async def test_unexpected_error_is_not_committed_or_sent_to_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = handler_module(monkeypatch)
    publish_to_dlq = AsyncMock()
    monkeypatch.setattr(module, "publish_to_dlq", publish_to_dlq)
    monkeypatch.setattr(module, "process_message", AsyncMock(side_effect=RuntimeError("DB down")))

    with pytest.raises(RuntimeError, match="DB down"):
        await module.handle_message(object(), object(), settings())

    publish_to_dlq.assert_not_awaited()
