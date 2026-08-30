from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from messaging_lab.messaging.contracts.base import (
    ContractModel,
    require_timezone_and_normalize_to_utc,
)


class PaymentRequestedV1(ContractModel):
    order_id: UUID
    amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"


class PaymentRequestedEnvelope(ContractModel):
    event_id: UUID
    event_type: Literal["payment.requested"] = "payment.requested"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: PaymentRequestedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class PaymentSucceededV1(ContractModel):
    payment_id: UUID
    order_id: UUID
    amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)


class PaymentFailedV1(ContractModel):
    payment_id: UUID
    order_id: UUID
    amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    failure_code: str = Field(min_length=1, max_length=100)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @field_validator("failure_code")
    @classmethod
    def validate_failure_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("failure_code must be non-empty")
        return value


class PaymentSucceededEnvelope(ContractModel):
    event_id: UUID
    event_type: Literal["payment.succeeded"] = "payment.succeeded"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: PaymentSucceededV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class PaymentFailedEnvelope(ContractModel):
    event_id: UUID
    event_type: Literal["payment.failed"] = "payment.failed"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: PaymentFailedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


type PaymentResultEnvelope = PaymentSucceededEnvelope | PaymentFailedEnvelope
