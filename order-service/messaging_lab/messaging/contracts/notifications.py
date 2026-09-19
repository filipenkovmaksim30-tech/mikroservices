from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from messaging_lab.messaging.contracts.base import (
    ContractModel,
    require_timezone_and_normalize_to_utc,
)


class OrderPaidV1(ContractModel):
    order_id: UUID
    receipt_email: EmailStr
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


class OrderPaidEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["order.paid"] = "order.paid"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: OrderPaidV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class OrderPaymentFailedV1(ContractModel):
    order_id: UUID
    receipt_email: EmailStr
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


class OrderPaymentFailedEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["order.payment_failed"] = "order.payment_failed"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: OrderPaymentFailedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


type OrderNotificationEnvelopeV1 = OrderPaidEnvelopeV1 | OrderPaymentFailedEnvelopeV1
