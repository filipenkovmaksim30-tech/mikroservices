
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.services.analytics_orders import AnalyticsOrderService
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.db.session import get_session
from analytics_service.schemas.analytics import AnalyticsSummaryResponse, DailySummaryResponse

router = APIRouter(tags=["Analytics"], prefix="/analytics")


def get_analytics_service(
    session: Annotated[AsyncSession, Depends(get_session)]
):
    analytics_repository = AnalyticsOrderRepository(session)
    analytics_service = AnalyticsOrderService(analytics_repository, session)
    return analytics_service
    

@router.get("/summary", response_model=AnalyticsSummaryResponse, summary="Получить выручку за период")
async def get_summary(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
) -> AnalyticsSummaryResponse:
    summary = await service.get_summary(date_from=date_from, date_to=date_to)
    return summary
    

@router.get("/summary-by-day", response_model=list[DailySummaryResponse], summary="Получить выручку по дням за период")
async def get_daily_summary(
    date_from: datetime,
    date_to: datetime,
    service: Annotated[AnalyticsOrderService, Depends(get_analytics_service)],
) -> list[DailySummaryResponse]:
    daily_summary = await service.get_daily_summary(date_from=date_from, date_to=date_to)
    return daily_summary
