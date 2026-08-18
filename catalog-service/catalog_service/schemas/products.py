
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ProductCreate(ContractModel):
    category: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=200)
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)


class ProductRead(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=200)
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)



