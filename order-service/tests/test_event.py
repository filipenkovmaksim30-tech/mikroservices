from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from pydantic import ValidationError

from messaging_lab.schemas.event import EventEnvelope, OrderCreatedV1, OrderItemV1


class EventContractTests(TestCase):
    def setUp(self) -> None:
        self.item = OrderItemV1(
            product_id=uuid4(),
            quantity=2,
            unit_price=Decimal("1500.00"),
        )

    def test_zero_quantity_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            OrderItemV1(
                product_id=uuid4(),
                quantity=0,
                unit_price=Decimal("1500.00"),
            )

    def test_incorrect_total_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            OrderCreatedV1(
                order_id=uuid4(),
                customer_id=uuid4(),
                items=[self.item],
                total_amount=Decimal("1.00"),
            )

    def test_datetime_without_timezone_is_rejected(self) -> None:
        payload = OrderCreatedV1(
            order_id=uuid4(),
            customer_id=uuid4(),
            items=[self.item],
            total_amount=Decimal("3000.00"),
        )

        with self.assertRaises(ValidationError):
            EventEnvelope[OrderCreatedV1](
                event_id=uuid4(),
                occurred_at=datetime.now(),
                correlation_id=uuid4(),
                payload=payload,
            )
