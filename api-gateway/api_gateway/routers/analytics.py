
from datetime import datetime

from fastapi import APIRouter, Depends, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    require_admin,
)
from api_gateway.schemas.analytics import AnalyticsSummaryResponse, DailySummaryResponse

router = APIRouter(
    tags=["Analytics"],
    prefix="/admin/analytics",
    dependencies=[Depends(require_admin)],
)

@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Получить выручку за период",
    status_code=status.HTTP_200_OK,
)
async def get_summary(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    date_from: datetime,
    date_to: datetime
) -> Response:
    url = f"{settings.analytics_base_url.rstrip("/")}/analytics/summary"

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        headers=authorization_headers,
    )
        

    return build_gateway_response(upstream_response)

@router.get(
    "/summary-by-day",
    response_model=list[DailySummaryResponse],
    summary="Получить выручку по дням за период",
    status_code=status.HTTP_200_OK,
)
async def get_daily_summary(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    date_from: datetime,
    date_to: datetime
) -> Response:
    url = f"{settings.analytics_base_url.rstrip("/")}/analytics/summary-by-day"

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        },
        headers=authorization_headers,
    )
    
    return build_gateway_response(upstream_response)

