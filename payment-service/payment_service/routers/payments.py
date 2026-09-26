from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from payment_service.db.models.payments import PaymentStatus
from payment_service.routers.dependencies import ServiceDependency, require_admin
from payment_service.schemas.payments import PaymentResponse

LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]

router = APIRouter(
    tags=["Payments"],
    prefix="/admin/payments",
    dependencies=[Depends(require_admin)]
)

@router.get(
    "/by-order/{order_id}",
    response_model=PaymentResponse,
    summary="Получить платеж по ID заказа",
    status_code=status.HTTP_200_OK,
)
async def get_payment_by_order_id(
    order_id: UUID,
    service: ServiceDependency,
):
    return await service.get_by_order_id(order_id)

@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Получить платеж по ID",
    status_code=status.HTTP_200_OK,
)
async def get_payment_by_id(
    payment_id: UUID,
    service: ServiceDependency,
):
    return await service.get_by_id(payment_id)


@router.get(
    "",
    response_model=list[PaymentResponse],
    summary="Получить все платежи с фильтром по статусу",
    status_code=status.HTTP_200_OK,
)
async def get_payments(
    service: ServiceDependency,
    status: PaymentStatus | None = None,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
):
    return await service.get_payments(status, limit, offset)
