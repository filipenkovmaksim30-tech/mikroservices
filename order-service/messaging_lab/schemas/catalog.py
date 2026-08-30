from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class CatalogBatchRequest(ContractModel):
    product_ids: set[UUID] = Field(min_length=1, max_length=100)


class CatalogProductSnapshot(ContractModel):
    id: UUID
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool

class CatalogBatchResponse(ContractModel):
    products: list[CatalogProductSnapshot]