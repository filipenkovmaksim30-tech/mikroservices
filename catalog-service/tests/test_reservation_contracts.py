from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationRequestedEnvelopeV1,
    StockReservationRequestedV1,
)


def test_reservation_request_rejects_duplicate_product_ids() -> None:
    product_id = uuid4()

    with pytest.raises(ValidationError, match="unique product_id"):
        StockReservationRequestedV1(
            order_id=uuid4(),
            items=[
                {"product_id": product_id, "quantity": 1},
                {"product_id": product_id, "quantity": 2},
            ],
        )


def test_reservation_request_rejects_wrong_correlation_id() -> None:
    with pytest.raises(ValidationError, match="correlation_id"):
        StockReservationRequestedEnvelopeV1(
            event_id=uuid4(),
            occurred_at=datetime.now(UTC),
            correlation_id=uuid4(),
            payload=StockReservationRequestedV1(
                order_id=uuid4(),
                items=[{"product_id": uuid4(), "quantity": 1}],
            ),
        )
