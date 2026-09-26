from datetime import UTC, datetime
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from catalog_service.exceptions import PermanentStockReservationFinalizationError
from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationConfirmRequestedEnvelopeV1,
    StockReservationConfirmRequestedV1,
)
from tests.test_reservations_db_integration import request_event


def incoming(body: bytes) -> SimpleNamespace:
    return SimpleNamespace(
        body=body,
        message_id="message-1",
        ack=AsyncMock(),
        reject=AsyncMock(),
    )


def session_factory() -> Mock:
    session = AsyncMock()
    session.__aenter__.return_value = object()
    return Mock(return_value=session)


def event_body(kind: str) -> bytes:
    order_id = uuid4()
    if kind == "reserve":
        event = request_event(order_id, {uuid4(): 2})
    else:
        event = StockReservationConfirmRequestedEnvelopeV1(
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            correlation_id=order_id,
            payload=StockReservationConfirmRequestedV1(order_id=order_id),
        )
    return event.model_dump_json().encode()


@pytest.mark.parametrize(
    ("module_name", "handler_name", "service_name", "kind"),
    [
        (
            "reservation_commands", "handle_reservation_requested",
            "StockReservationService", "reserve",
        ),
        (
            "reservation_finalization", "handle_finalization_requested",
            "StockReservationFinalizationService", "confirm",
        ),
    ],
)
async def test_consumer_acks_only_after_service_success(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    handler_name: str,
    service_name: str,
    kind: str,
) -> None:
    module = import_module(f"catalog_service.consumers.{module_name}")
    process = AsyncMock()
    monkeypatch.setattr(module, service_name, lambda **_kwargs: SimpleNamespace(process=process))
    message = incoming(event_body(kind))

    await getattr(module, handler_name)(message, session_factory(), object(), "catalog-test")

    process.assert_awaited_once()
    message.ack.assert_awaited_once()
    message.reject.assert_not_awaited()


@pytest.mark.parametrize(
    ("module_name", "handler_name"),
    [
        ("reservation_commands", "handle_reservation_requested"),
        ("reservation_finalization", "handle_finalization_requested"),
    ],
)
async def test_invalid_payload_is_rejected_without_db_session(
    module_name: str, handler_name: str
) -> None:
    module = import_module(f"catalog_service.consumers.{module_name}")
    message = incoming(b"not JSON")
    factory = session_factory()

    await getattr(module, handler_name)(message, factory, object(), "catalog-test")

    factory.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


async def test_permanent_finalization_error_rejected_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = import_module("catalog_service.consumers.reservation_finalization")
    process = AsyncMock(side_effect=PermanentStockReservationFinalizationError("bad state"))
    retry = AsyncMock()
    monkeypatch.setattr(
        module, "StockReservationFinalizationService",
        lambda **_kwargs: SimpleNamespace(process=process),
    )
    monkeypatch.setattr(module, "retry_or_send_to_dlq", retry)
    message = incoming(event_body("confirm"))

    await module.handle_finalization_requested(
        message, session_factory(), object(), "catalog-test"
    )

    message.reject.assert_awaited_once_with(requeue=False)
    retry.assert_not_awaited()
    message.ack.assert_not_awaited()


@pytest.mark.parametrize(
    ("module_name", "handler_name", "service_name", "kind"),
    [
        (
            "reservation_commands", "handle_reservation_requested",
            "StockReservationService", "reserve",
        ),
        (
            "reservation_finalization", "handle_finalization_requested",
            "StockReservationFinalizationService", "confirm",
        ),
    ],
)
async def test_transient_error_goes_to_retry_without_ack(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    handler_name: str,
    service_name: str,
    kind: str,
) -> None:
    module = import_module(f"catalog_service.consumers.{module_name}")
    process = AsyncMock(side_effect=OSError("database unavailable"))
    retry = AsyncMock()
    monkeypatch.setattr(module, service_name, lambda **_kwargs: SimpleNamespace(process=process))
    monkeypatch.setattr(module, "retry_or_send_to_dlq", retry)
    message = incoming(event_body(kind))

    await getattr(module, handler_name)(message, session_factory(), object(), "catalog-test")

    retry.assert_awaited_once()
    assert retry.await_args.kwargs["event_id"]
    message.ack.assert_not_awaited()
