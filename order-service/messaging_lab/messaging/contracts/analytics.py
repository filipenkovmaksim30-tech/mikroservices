from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from messaging_lab.messaging.contracts.base import (
    ContractModel,
    require_timezone_and_normalize_to_utc,
)


class AnalyticsOrderItemV1(ContractModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

    @field_validator("unit_price", mode="before")
    @classmethod
    def reject_float_price(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("unit_price must be Decimal, not float")
        return value


class OrderCreatedAnalyticsV1(ContractModel):
    order_id: UUID
    customer_id: UUID
    total_amount: Decimal = Field(ge=0)
    items: list[AnalyticsOrderItemV1] = Field(min_length=1)

    @field_validator("total_amount", mode="before")
    @classmethod
    def reject_float_total_amount(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("total_amount must be Decimal, not float")
        return value

    @model_validator(mode="after")
    def validate_total_amount(self) -> Self:
        calculated_total = sum(
            (item.quantity * item.unit_price for item in self.items),
            start=Decimal("0"),
        )
        if self.total_amount != calculated_total:
            raise ValueError(f"total_amount must equal {calculated_total}")
        return self


class AnalyticsEventEnvelope[PayloadT: BaseModel](ContractModel):
    event_id: UUID
    event_type: Literal["order.created"]
    event_version: Literal[1]
    occurred_at: datetime
    correlation_id: UUID
    payload: PayloadT

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)



class AnalyticsOrderPaidV1(ContractModel):
    order_id: UUID
    customer_id: UUID
    total_amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    paid_at: datetime

    @field_validator("total_amount", mode="before")
    @classmethod
    def reject_total_amount(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("total_amount must be Decimal not float")
        return value

    @field_validator("paid_at")
    @classmethod
    def validate_paid_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)


class AnalyticsOrderPaidEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["order.paid"] = "order.paid"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: AnalyticsOrderPaidV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class AnalyticsOrderPaymentFailedV1(ContractModel):
    order_id: UUID
    customer_id: UUID
    total_amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    failed_at: datetime
    failure_code: str = Field(min_length=1, max_length=100)

    @field_validator("total_amount", mode="before")
    @classmethod
    def reject_total_amount(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("total_amount must be Decimal not float")
        return value

    @field_validator("failed_at")
    @classmethod
    def validate_failed_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @field_validator("failure_code")
    @classmethod
    def validate_failure_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("failure_code must be non-empty")
        return value


class AnalyticsOrderPaymentFailedEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["order.payment_failed"] = "order.payment_failed"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: AnalyticsOrderPaymentFailedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self
