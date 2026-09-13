from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from api_gateway.api_clients.http import build_gateway_response, request_upstream
from api_gateway.routers.dependencies import (
    AuthorizationHeadersDependency,
    HttpClientDependency,
    SettingsDependency,
    require_admin,
)
from api_gateway.schemas.orders import OrderRead

router = APIRouter(
    tags=["Admin Orders"], 
    prefix="/admin/orders", 
    dependencies=[Depends(require_admin)]
)

@router.get(
    "/{order_id}",
    response_model=OrderRead,
    status_code=status.HTTP_200_OK,
    summary="Найти заказ по ID"
)

async def get_order(
    authorization_headers: AuthorizationHeadersDependency,
    order_id: UUID,
    client: HttpClientDependency,
    settings: SettingsDependency,
) -> Response:
        
    url = (
        f"{settings.orders_base_url.rstrip("/")}"
        f"/admin/orders/{order_id}"
    )

    upstream_response = await request_upstream(
        client=client,
        method="GET",
        url=url,
        headers=authorization_headers,
    )
    
    return build_gateway_response(upstream_response)
