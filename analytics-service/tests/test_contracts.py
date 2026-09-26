from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from analytics_service.messaging.contract import (
    AnalyticsEventEnvelope,
    OrderCreatedAnalyticsV1,
)


def test_order_created_contract_rejects_incorrect_total() -> None:
    with pytest.raises(ValidationError, match="Итоговая сумма"):
        OrderCreatedAnalyticsV1(
            order_id=uuid4(),
            customer_id=uuid4(),
            total_amount=Decimal("1.00"),
            items=[{"product_id": uuid4(), "quantity": 2, "unit_price": "100.00"}],
        )


def test_order_created_contract_rejects_naive_timestamp() -> None:
    payload = OrderCreatedAnalyticsV1(
        order_id=uuid4(),
        customer_id=uuid4(),
        total_amount=Decimal("100.00"),
        items=[{"product_id": uuid4(), "quantity": 1, "unit_price": "100.00"}],
    )
    with pytest.raises(ValidationError, match="часовом поясе"):
        AnalyticsEventEnvelope[OrderCreatedAnalyticsV1](
            event_id=uuid4(),
            event_type="order.created",
            event_version=1,
            occurred_at=datetime.now().replace(tzinfo=None),
            correlation_id=payload.order_id,
            payload=payload,
        )


def test_order_created_contract_accepts_aware_timestamp() -> None:
    payload = OrderCreatedAnalyticsV1(
        order_id=uuid4(),
        customer_id=uuid4(),
        total_amount=Decimal("100.00"),
        items=[{"product_id": uuid4(), "quantity": 1, "unit_price": "100.00"}],
    )
    event = AnalyticsEventEnvelope[OrderCreatedAnalyticsV1](
        event_id=uuid4(),
        event_type="order.created",
        event_version=1,
        occurred_at=datetime.now(UTC),
        correlation_id=payload.order_id,
        payload=payload,
    )
    assert event.payload.total_amount == Decimal("100.00")
