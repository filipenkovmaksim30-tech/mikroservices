from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    orders_count: int = Field(ge=0)
    revenue: Decimal = Field(ge=0)
    average_order_value: Decimal = Field(ge=0)
    items_quantity: int = Field(ge=0)

class DailySummaryResponse(AnalyticsSummaryResponse):
    day: date