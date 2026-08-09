from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.order import Order
from messaging_lab.db.session import get_session
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository
from messaging_lab.repositories.products import ProductRepository
from messaging_lab.schemas.order import OrderCreate, OrderRead
from messaging_lab.services.orders import CreateOrderItem, OrderService


router = APIRouter(tags=["Orders"], prefix="/orders")

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_order_service(session: SessionDependency) -> OrderService:
    return OrderService(
        session=session,
        order_repository=OrderRepository(session),
        product_repository=ProductRepository(session),
        rabbitmq_outbox_repository=RabbitMQOutboxRepository(session),
        kafka_outbox_repository=KafkaOutboxRepository(session)
    )


OrderServiceDependency = Annotated[OrderService, Depends(get_order_service)]


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый заказ",
)
async def create_order(
    data: OrderCreate,
    service: OrderServiceDependency,
) -> Order:
    items = [
        CreateOrderItem(
            product_id=item.product_id,
            quantity=item.quantity,
        )
        for item in data.items
    ]
    return await service.create_order(customer_id=data.customer_id, receipt_email=str(data.receipt_email), items=items)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    status_code=status.HTTP_200_OK,
    summary="Получить заказ по ID",
)
async def get_order(
    order_id: UUID,
    service: OrderServiceDependency,
) -> Order:
    return await service.get_order(order_id)
