from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from payment_service.integrations.fake_payment import FakePaymentProvider
from payment_service.messaging.contracts import PaymentRequestedEnvelope, PaymentRequestedV1
from payment_service.services.payment_provider import PaymentResult


@pytest.mark.parametrize(
    ("succeeded", "failure_code"),
    [(True, "declined"), (False, None), (False, "   ")],
)
def test_payment_result_rejects_inconsistent_data(
    succeeded: bool, failure_code: str | None
) -> None:
    with pytest.raises(ValueError):
        PaymentResult(succeeded=succeeded, failure_code=failure_code)


def test_payment_request_requires_matching_correlation_id() -> None:
    with pytest.raises(ValidationError, match="correlation_id"):
        PaymentRequestedEnvelope(
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            correlation_id=uuid4(),
            payload=PaymentRequestedV1(
                order_id=uuid4(), amount=Decimal("100.00"), currency="RUB"
            ),
        )


@pytest.mark.parametrize("should_succeed", [True, False])
async def test_fake_provider_has_deterministic_result(should_succeed: bool) -> None:
    provider = FakePaymentProvider(should_succeed=should_succeed, delay_seconds=0)

    result = await provider.charge(
        idempotency_key=uuid4(),
        order_id=uuid4(),
        amount=Decimal("100.00"),
        currency="RUB",
    )

    assert result.succeeded is should_succeed
    assert result.failure_code == (None if should_succeed else "payment_declined")
