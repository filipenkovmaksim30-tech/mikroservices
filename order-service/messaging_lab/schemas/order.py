from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from messaging_lab.db.models.order import OrderStatus


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderItemCreate(ContractModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class OrderCreate(ContractModel):
    customer_id: UUID
    receipt_email: EmailStr
    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)


class OrderItemRead(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class OrderRead(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    receipt_email: EmailStr
    total_amount: Decimal = Field(ge=0)
    status: OrderStatus
    created_at: datetime
    items: list[OrderItemRead]
