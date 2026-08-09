from datetime import UTC, datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderItemV1(ContractModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)

    @field_validator("unit_price", mode="before")
    @classmethod
    def reject_float_price(cls, value: object):
        if isinstance(value, float):
            raise ValueError("Цена должна быть Decimal не float")
        return value



class OrderCreatedV1(ContractModel):
    order_id: UUID
    customer_id: UUID
    receipt_email: EmailStr
    items: list[OrderItemV1] = Field(min_length=1)
    total_amount: Decimal = Field(ge=0)

    @field_validator("total_amount", mode="before")
    @classmethod
    def reject_total_amount(cls, value):
        if isinstance(value, float):
            raise ValueError("Общая сумма заказа должна быть Decimal не float")
        return value
    
    @model_validator(mode="after")
    def validate_total_amount(self):
        calculate_total = sum(
            (item.quantity * item.unit_price for item in self.items),
            start=Decimal("0")
        )
        if self.total_amount != calculate_total:
            raise ValueError(f"Итоговая сумма не равна {calculate_total}")
        return self


class EventEnvelope(ContractModel, Generic[PayloadT]):
    event_id: UUID
    event_type: Literal["order.created"] = "order.created"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: PayloadT

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_and_normalize_to_utc(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at должен содержать о часовом поясе")
        return value.astimezone(UTC)

