from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentStatusResponse(BaseModel):
    order_id: UUID
    amount: Decimal = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    status: str
