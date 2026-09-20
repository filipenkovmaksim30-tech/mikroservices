from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    orders_count: int = Field(ge=0, description="Orders created during the period")
    paid_orders_count: int = Field(ge=0)
    payment_failed_count: int = Field(ge=0)
    revenue: Decimal = Field(ge=0, description="Total amount of paid orders")
    average_order_value: Decimal = Field(ge=0, description="Average amount of paid orders")
    items_quantity: int = Field(ge=0, description="Units in paid orders")


class TopProductResponse(BaseModel):
    product_id: UUID
    orders_count: int = Field(gt=0)
    units_ordered: int = Field(gt=0)
    revenue: Decimal = Field(ge=0)


class CustomerSummaryResponse(AnalyticsSummaryResponse):
    customer_id: UUID
    first_order_at: datetime | None
    last_order_at: datetime | None


class DailySummaryResponse(AnalyticsSummaryResponse):
    day: date
