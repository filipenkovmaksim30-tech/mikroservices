from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from analytics_service.schemas.analytics import (
    AnalyticsSummaryResponse,
    DailySummaryResponse,
    RevenueByDayResponse,
    TopProductResponse,
)
from analytics_service.services.analytics_orders import AnalyticsOrderService

from analytics_service.routers.dependencies import get_analytics_service, require_admin

router = APIRouter(tags=["Analytics"], prefix="/analytics", dependencies=[Depends(require_admin)])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Сводка по заказам, созданным за период",
)
async def get_summary(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
) -> AnalyticsSummaryResponse:
    summary = await service.get_summary(date_from=date_from, date_to=date_to)
    return summary
    

@router.get(
    "/summary-by-day",
    response_model=list[DailySummaryResponse],
    summary="Сводка по UTC-дням создания заказов",
)
async def get_daily_summary(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
) -> list[DailySummaryResponse]:
    daily_summary = await service.get_daily_summary(date_from=date_from, date_to=date_to)
    return daily_summary


@router.get(
    "/products/top",
    response_model=list[TopProductResponse],
    summary="Топ товаров по оплаченным заказам",
)
async def get_top_products(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    sort_by: Literal["quantity", "revenue"] = "quantity",
) -> list[TopProductResponse]:
    return await service.get_top_products(
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        sort_by=sort_by,
    )


@router.get(
    "/revenue-by-day",
    response_model=list[RevenueByDayResponse],
    summary="Выручка по UTC-дням оплаты",
)
async def get_revenue_by_day(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
) -> list[RevenueByDayResponse]:
    return await service.get_revenue_by_day(date_from=date_from, date_to=date_to)
