
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    require_admin,
)
from api_gateway.schemas.analytics import AnalyticsSummaryResponse, DailySummaryResponse, RevenueByDayResponse, TopProductResponse


router = APIRouter(
    tags=["Analytics"],
    prefix="/admin/analytics",
    dependencies=[Depends(require_admin)],
)

LimitQuery = Annotated[int, Query(ge=1, le=50)]

@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Сводка по заказам, созданным за период",
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
    summary="Сводка по UTC-дням создания заказов",
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

@router.get(
    "/products/top",
    response_model=list[TopProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Топ товаров по оплаченным заказам"
)
async def get_top_products(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    date_from: datetime,
    date_to: datetime,
    limit: LimitQuery = 10,
    sort_by: Literal["quantity", "revenue"] = "quantity"
):
    url = f"{settings.analytics_base_url.rstrip("/")}/analytics/products/top"
    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "limit": limit,
            "sort_by": sort_by,
        },
        headers=authorization_headers,
    )
    return build_gateway_response(upstream_response)


@router.get(
    "/revenue-by-day",
    response_model=list[RevenueByDayResponse],
    status_code=status.HTTP_200_OK,
    summary="Выручка по UTC-дням оплаты",
)
async def get_revenue_by_day(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    date_from: datetime,
    date_to: datetime,
):
    url = f"{settings.analytics_base_url.rstrip("/")}/analytics/revenue-by-day"
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