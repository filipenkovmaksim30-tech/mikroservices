from datetime import UTC, datetime
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from messaging_lab.messaging.contracts.notifications import OrderPaidEnvelopeV1, OrderPaidV1
from messaging_lab.messaging.contracts.payments import PaymentSucceededEnvelope, PaymentSucceededV1
from tests.test_order_result_services import stock_reserved_event


def body(kind: str) -> bytes:
    order_id = uuid4()
    now = datetime.now(UTC)
    if kind == "payment":
        event = PaymentSucceededEnvelope(
            event_id=uuid4(), occurred_at=now, correlation_id=order_id,
            payload=PaymentSucceededV1(
                payment_id=uuid4(), order_id=order_id, amount="100.00",
                currency="RUB", completed_at=now,
            ),
        )
    elif kind == "stock":
        event = stock_reserved_event(order_id)
    else:
        event = OrderPaidEnvelopeV1(
            event_id=uuid4(), occurred_at=now, correlation_id=order_id,
            payload=OrderPaidV1(
                order_id=order_id, receipt_email="buyer@example.com",
                total_amount="100.00", currency="RUB", paid_at=now,
            ),
        )
    return event.model_dump_json().encode()


def incoming(payload: bytes) -> SimpleNamespace:
    return SimpleNamespace(
        body=payload, headers=None, message_id="message-1",
        ack=AsyncMock(), reject=AsyncMock(),
    )


def session_factory() -> Mock:
    session = AsyncMock()
    session.__aenter__.return_value = object()
    return Mock(return_value=session)


@pytest.mark.parametrize(
    ("module_name", "handler_name", "service_name", "kind"),
    [
        ("payment_result", "handler_payment_result", "PaymentResultService", "payment"),
        (
            "reservation_result", "handler_stock_reservation_result",
            "StockReservationResultService", "stock",
        ),
    ],
)
async def test_result_consumer_acks_after_service_success(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str, handler_name: str, service_name: str, kind: str,
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    process = AsyncMock()
    monkeypatch.setattr(module, service_name, lambda **_kwargs: SimpleNamespace(process=process))
    message = incoming(body(kind))

    await getattr(module, handler_name)(message, object(), "order-test", session_factory())

    process.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.reject.assert_not_awaited()


@pytest.mark.parametrize(
    ("module_name", "handler_name"),
    [
        ("payment_result", "handler_payment_result"),
        ("reservation_result", "handler_stock_reservation_result"),
    ],
)
async def test_invalid_result_rejects_without_database(
    module_name: str, handler_name: str,
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    message = incoming(b"not-json")
    factory = session_factory()

    await getattr(module, handler_name)(message, object(), "order-test", factory)

    factory.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.parametrize(
    ("module_name", "handler_name", "service_name", "kind"),
    [
        ("payment_result", "handler_payment_result", "PaymentResultService", "payment"),
        (
            "reservation_result", "handler_stock_reservation_result",
            "StockReservationResultService", "stock",
        ),
    ],
)
async def test_temporary_result_error_retries_without_ack(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str, handler_name: str, service_name: str, kind: str,
) -> None:
    module = import_module(f"messaging_lab.consumers.{module_name}")
    process = AsyncMock(side_effect=OSError("DB down"))
    retry = AsyncMock()
    monkeypatch.setattr(module, service_name, lambda **_kwargs: SimpleNamespace(process=process))
    monkeypatch.setattr(module, "retry_or_send_to_dlq", retry)
    message = incoming(body(kind))

    await getattr(module, handler_name)(message, object(), "order-test", session_factory())

    retry.assert_awaited_once()
    message.ack.assert_not_awaited()


async def test_notification_acks_after_process(monkeypatch: pytest.MonkeyPatch) -> None:
    module = import_module("messaging_lab.consumers.notifications")
    process = AsyncMock(return_value=True)
    monkeypatch.setattr(module, "process_with_inbox", process)
    message = incoming(body("notification"))

    await module.handle_notification(message, object(), object(), session_factory())

    process.assert_awaited_once()
    message.ack.assert_awaited_once()


async def test_notification_invalid_payload_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    module = import_module("messaging_lab.consumers.notifications")
    process = AsyncMock()
    monkeypatch.setattr(module, "process_with_inbox", process)
    message = incoming(b"bad-json")

    await module.handle_notification(message, object(), object(), session_factory())

    process.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)


async def test_notification_transient_error_retries_without_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("messaging_lab.consumers.notifications")
    monkeypatch.setattr(
        module, "process_with_inbox",
        AsyncMock(side_effect=module.TransientNotificationError("SMTP down")),
    )
    retry = AsyncMock()
    monkeypatch.setattr(module, "retry_or_send_to_dlq", retry)
    message = incoming(body("notification"))

    await module.handle_notification(message, object(), object(), session_factory())

    retry.assert_awaited_once()
    message.ack.assert_not_awaited()
