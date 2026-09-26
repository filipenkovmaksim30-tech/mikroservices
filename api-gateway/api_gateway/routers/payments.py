

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from api_gateway.routers.dependencies import (
    SettingsDependency,
    HttpClientDependency,
    AuthorizationHeadersDependency,
    require_admin,
)
from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.schemas.payments import PaymentResponse, PaymentStatus

router = APIRouter(
    tags=["Admin Payments"], 
    prefix="/admin/payments",
    dependencies=[Depends(require_admin)]
)

LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]



@router.get(
    "/by-order/{order_id}",
    response_model=PaymentResponse,
    summary="Получить платеж по ID заказа",
    status_code=status.HTTP_200_OK,
)
async def get_payment_by_order_id(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    order_id: UUID
):
    url = (
        f"{settings.payment_base_url.rstrip("/")}"
        f"/admin/payments/by-order/{order_id}"
    )

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        headers=authorization_headers,
    )
    return build_gateway_response(upstream_response)

@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Получить платеж по ID",
    status_code=status.HTTP_200_OK,
)
async def get_payment_by_id(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    payment_id: UUID
):
    url = (
        f"{settings.payment_base_url.rstrip("/")}"
        f"/admin/payments/{payment_id}"
    )

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        headers=authorization_headers,
    )
    return build_gateway_response(upstream_response)

@router.get(
    "",
    response_model=list[PaymentResponse],
    summary="Получить все платежи с фильтром по статусу",
    status_code=status.HTTP_200_OK,
)
async def get_payments(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    status: PaymentStatus | None = None,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
):
    url = (
        f"{settings.payment_base_url.rstrip("/")}"
        f"/admin/payments"
    )

    params = {"limit": limit, "offset": offset}
    if status is not None:
        params["status"] = status.value

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params=params,
        headers=authorization_headers,
    )
    return build_gateway_response(upstream_response)