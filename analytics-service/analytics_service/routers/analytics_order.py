from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from analytics_service.schemas.analytics import AnalyticsSummaryResponse, DailySummaryResponse
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
