from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    orders_count: int = Field(ge=0, description="Orders created during the period")
    paid_orders_count: int = Field(ge=0)
    payment_failed_count: int = Field(ge=0)
    revenue: Decimal = Field(ge=0, description="Total amount of paid orders")
    average_order_value: Decimal = Field(ge=0, description="Average amount of paid orders")
    items_quantity: int = Field(ge=0, description="Units in paid orders")

class DailySummaryResponse(AnalyticsSummaryResponse):
    day: date
