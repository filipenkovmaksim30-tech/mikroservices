from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ProductCreate(ContractModel):
    category: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=200)
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)

class ProductUpdate(ContractModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=200)
    price: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        non_nullable_fields = {"category", "name", "price"}

        null_fields = {
            field_name
            for field_name in self.model_fields_set
            if (
                field_name in non_nullable_fields
                and getattr(self, field_name) is None
            )
        }

        if null_fields:
            raise ValueError(
                f"Fields cannot be null: {sorted(null_fields)}"
            )

        return self

class ProductRead(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=200)
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool

class ProductBatchRequest(ContractModel):
    product_ids: set[UUID] = Field(min_length=1, max_length=100)


class ProductSnapshot(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool

class ProductBatchResponse(ContractModel):
    products: list[ProductSnapshot]


class ProductListResponse(ContractModel):
    items: list[ProductRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

