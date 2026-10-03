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
    price: Decimal = Field(gt=0, decimal_places=2)
    stock_quantity: int = Field(ge=0)

class ProductUpdate(ContractModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=200)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)

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
    price: Decimal = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool

class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    position: int = Field(ge=0)


class ProductImageOrderUpdate(ContractModel):
    image_ids: list[UUID] = Field(max_length=8)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        if len(self.image_ids) != len(set(self.image_ids)):
            raise ValueError("image_ids must not contain duplicates")
        return self


class ProductImagePublicRead(ProductImageRead):
    url: str
    thumbnail_url: str


class ProductPublicRead(ProductRead):
    images: list[ProductImagePublicRead]
    model_3d_url: str | None


class ProductModelRead(ContractModel):
    model_3d_url: str

class ProductBatchRequest(ContractModel):
    product_ids: set[UUID] = Field(min_length=1, max_length=100)


class ProductSnapshot(ContractModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    price: Decimal = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool

class ProductBatchResponse(ContractModel):
    products: list[ProductSnapshot]


class ProductListResponse(ContractModel):
    items: list[ProductPublicRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)

