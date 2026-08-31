from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from catalog_service.messaging.contracts.base import (
    ContractModel,
    require_timezone_and_normalize_to_utc,
)

type StockReservationFailureCode = Literal[
    "product_not_found",
    "product_inactive",
    "insufficient_stock",
]


class StockReservationItemV1(ContractModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class StockReservationRequestedV1(ContractModel):
    order_id: UUID
    items: list[StockReservationItemV1] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_product_ids(self) -> Self:
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("items must contain unique product_id values")
        return self


class StockReservationRequestedEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["stock.reservation.requested"] = "stock.reservation.requested"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: StockReservationRequestedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class StockReservedV1(ContractModel):
    reservation_id: UUID
    order_id: UUID
    reserved_at: datetime

    @field_validator("reserved_at")
    @classmethod
    def validate_reserved_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)


class StockReservationFailedV1(ContractModel):
    order_id: UUID
    failure_code: StockReservationFailureCode
    failed_product_ids: set[UUID] = Field(min_length=1)
    failed_at: datetime

    @field_validator("failed_at")
    @classmethod
    def validate_failed_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)


class StockReservedEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["stock.reserved"] = "stock.reserved"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: StockReservedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


class StockReservationFailedEnvelopeV1(ContractModel):
    event_id: UUID
    event_type: Literal["stock.reservation.failed"] = "stock.reservation.failed"
    event_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: UUID
    payload: StockReservationFailedV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return require_timezone_and_normalize_to_utc(value)

    @model_validator(mode="after")
    def validate_correlation_id(self) -> Self:
        if self.correlation_id != self.payload.order_id:
            raise ValueError("correlation_id must match payload.order_id")
        return self


type StockReservationResultEnvelopeV1 = (
    StockReservedEnvelopeV1 | StockReservationFailedEnvelopeV1
)
