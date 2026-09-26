from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiosmtplib import SMTPAuthenticationError, SMTPResponseException

from messaging_lab.integrations import smtp as smtp_module
from messaging_lab.messaging.contracts.notifications import (
    OrderPaidEnvelopeV1,
    OrderPaymentFailedEnvelopeV1,
    OrderPaymentFailedV1,
)
from messaging_lab.services.notifications import (
    PermanentNotificationError,
    TransientNotificationError,
)
from tests.test_order_consumers import body


def provider() -> smtp_module.GmailSmtpNotificationProvider:
    return smtp_module.GmailSmtpNotificationProvider(
        port=587, host="smtp.test", username="user", password="test-password",
        sender_email="sender@example.com", start_tls=True, use_tls=False,
        timeout_seconds=5,
    )


def failed_event() -> OrderPaymentFailedEnvelopeV1:
    order_id = uuid4()
    now = datetime.now(UTC)
    return OrderPaymentFailedEnvelopeV1(
        event_id=uuid4(), occurred_at=now, correlation_id=order_id,
        payload=OrderPaymentFailedV1(
            order_id=order_id, receipt_email="buyer@example.com",
            total_amount="100.00", failed_at=now, failure_code="declined",
        ),
    )


@pytest.mark.parametrize("failed", [False, True])
async def test_email_content_and_metadata_without_real_smtp(
    monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    send = AsyncMock()
    monkeypatch.setattr(smtp_module.aiosmtplib, "send", send)
    event = (
        failed_event()
        if failed
        else OrderPaidEnvelopeV1.model_validate_json(body("notification"))
    )

    await provider().send_order_notifications(event, "event-id")

    message = send.await_args.args[0]
    assert message["To"] == "buyer@example.com"
    assert message["X-Idempotency-Key"] == "event-id"
    assert ("не прошла" if failed else "прошла успешно") in message.get_content()
    assert send.await_args.kwargs["hostname"] == "smtp.test"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OSError("connection lost"), TransientNotificationError),
        (SMTPResponseException(421, "try later"), TransientNotificationError),
        (SMTPResponseException(550, "bad recipient"), PermanentNotificationError),
        (SMTPAuthenticationError(535, "bad credentials"), PermanentNotificationError),
    ],
)
async def test_smtp_errors_are_classified(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: type[Exception]
) -> None:
    monkeypatch.setattr(smtp_module.aiosmtplib, "send", AsyncMock(side_effect=error))
    event = OrderPaidEnvelopeV1.model_validate_json(body("notification"))

    with pytest.raises(expected):
        await provider().send_order_notifications(event, "event-id")


def test_smtp_rejects_conflicting_tls_modes() -> None:
    with pytest.raises(ValueError, match="cannot both be enabled"):
        smtp_module.GmailSmtpNotificationProvider(
            port=465, host="smtp.test", username="user", password="password",
            sender_email="sender@example.com", start_tls=True, use_tls=True,
            timeout_seconds=5,
        )
