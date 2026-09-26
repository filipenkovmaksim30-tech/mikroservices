from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from payment_service.consumers import order_payment as consumer
from payment_service.exceptions import PaymentRequestConflictError
from tests.test_payment_processing import payment_requested_event


def incoming(body: bytes, headers: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        body=body, headers=headers, message_id="event-1",
        ack=AsyncMock(), reject=AsyncMock(),
    )


def session_factory() -> Mock:
    session = AsyncMock()
    session.__aenter__.return_value = object()
    return Mock(return_value=session)


async def test_valid_payment_command_acks_after_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    process = AsyncMock()
    monkeypatch.setattr(
        consumer, "PaymentProcessingService", lambda **_kwargs: SimpleNamespace(process=process)
    )
    message = incoming(payment_requested_event().model_dump_json().encode())

    await consumer.handle_payment_requested(message, object(), "payment-test", session_factory())

    process.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.reject.assert_not_awaited()


async def test_invalid_payment_command_goes_to_dlq_without_db() -> None:
    message = incoming(b"not-json")
    factory = session_factory()

    await consumer.handle_payment_requested(message, object(), "payment-test", factory)

    factory.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.parametrize("error", [OSError("DB down"), RuntimeError("unexpected")])
async def test_processing_error_goes_to_retry_without_ack(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    process = AsyncMock(side_effect=error)
    retry = AsyncMock()
    monkeypatch.setattr(
        consumer, "PaymentProcessingService", lambda **_kwargs: SimpleNamespace(process=process)
    )
    monkeypatch.setattr(consumer, "retry_or_send_to_dlq", retry)
    message = incoming(payment_requested_event().model_dump_json().encode())

    await consumer.handle_payment_requested(message, object(), "payment-test", session_factory())

    retry.assert_awaited_once()
    message.ack.assert_not_awaited()


async def test_conflicting_payment_command_is_rejected_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = AsyncMock(side_effect=PaymentRequestConflictError(
        uuid4(), Decimal("100"), Decimal("200"), "RUB", "RUB"
    ))
    retry = AsyncMock()
    monkeypatch.setattr(
        consumer, "PaymentProcessingService", lambda **_kwargs: SimpleNamespace(process=process)
    )
    monkeypatch.setattr(consumer, "retry_or_send_to_dlq", retry)
    message = incoming(payment_requested_event().model_dump_json().encode())

    await consumer.handle_payment_requested(message, object(), "payment-test", session_factory())

    message.reject.assert_awaited_once_with(requeue=False)
    retry.assert_not_awaited()
    message.ack.assert_not_awaited()


async def test_retry_publishes_before_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    message = incoming(b"original", {"x-retry-count": 1})
    publish = AsyncMock()
    monkeypatch.setattr(consumer, "publish_message", publish)

    await consumer.retry_or_send_to_dlq(message, object(), "retry", "event-1", "order-1")

    assert publish.await_args.kwargs["headers"] == {"x-retry-count": 2}
    message.ack.assert_awaited_once()


@pytest.mark.parametrize("headers", [{"x-retry-count": 3}, {"x-retry-count": "invalid"}])
async def test_retry_limit_or_invalid_header_rejects(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, object]
) -> None:
    message = incoming(b"original", headers)
    publish = AsyncMock()
    monkeypatch.setattr(consumer, "publish_message", publish)

    await consumer.retry_or_send_to_dlq(message, object(), "retry", "event-1", "order-1")

    publish.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


async def test_failed_retry_publish_rejects_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    message = incoming(b"original")
    monkeypatch.setattr(
        consumer, "publish_message", AsyncMock(side_effect=OSError("broker down"))
    )

    await consumer.retry_or_send_to_dlq(message, object(), "retry", "event-1", "order-1")

    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()
