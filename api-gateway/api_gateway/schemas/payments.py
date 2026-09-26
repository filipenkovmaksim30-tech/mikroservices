from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    order_id: UUID
    amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    status: str
    failure_code: str | None
    created_at: datetime
    completed_at: datetime | None

class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"