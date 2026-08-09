from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    def require_timezone_and_normalize_to_utc(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at должен содержать информацию о часовом поясе")
        return value.astimezone(UTC)