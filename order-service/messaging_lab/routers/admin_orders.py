from uuid import UUID

from fastapi import APIRouter, status, Depends

from messaging_lab.schemas.order import OrderRead
from messaging_lab.routers.dependencies import OrderServiceDependency, require_admin
from messaging_lab.db.models.order import Order

router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"], dependencies=[Depends(require_admin)])

@router.get(
    "/{order_id}",
    response_model=OrderRead,
    status_code=status.HTTP_200_OK,
    summary="Получить заказ по ID (Админ)",
)
async def get_order(
    order_id: UUID,
    service: OrderServiceDependency,
) -> Order:
    return await service.get_order(order_id)