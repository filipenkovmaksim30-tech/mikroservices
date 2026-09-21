from typing import Annotated

from fastapi import APIRouter, Query, Header, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    ForwardedHeadersDependency
)
from api_gateway.schemas.orders import OrderCreate, OrderRead

LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]

router = APIRouter(tags=["Orders"], prefix="/orders")



@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=OrderRead,
    summary="Создать новый заказ",
)
async def create_order(
    authorization_headers: AuthorizationHeadersDependency,
    forwarded_headers: ForwardedHeadersDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    payload: OrderCreate,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
    url = f"{settings.orders_base_url.rstrip("/")}/orders"

    upstream_response = await request_upstream(
        client=client,
        method="POST",
        url=url,
        json_body=payload.model_dump(mode="json"),
        headers={
            **authorization_headers,
            **forwarded_headers,
            "Idempotency-Key": idempotency_key,
        }
    )

    return build_gateway_response(upstream_response)

@router.get(
    "/my",
    response_model=list[OrderRead],
    status_code=status.HTTP_200_OK,
    summary="Получить мои заказы",
)
async def get_my_orders(
    authorization_headers: AuthorizationHeadersDependency,
    client: HttpClientDependency,
    settings: SettingsDependency,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
) -> Response:
    url = f"{settings.orders_base_url.rstrip("/")}/orders/my"

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        params={
            "limit": limit,
            "offset": offset,
        },
        headers=authorization_headers,
            
    )
    return build_gateway_response(upstream_response)
