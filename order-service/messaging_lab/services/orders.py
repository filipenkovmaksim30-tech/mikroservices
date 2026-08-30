from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.models.kafka_outbox import KafkaOutboxEvent
from messaging_lab.db.models.order import Order
from messaging_lab.db.models.order_item import OrderItem
from messaging_lab.db.models.rabbitmq_outbox import RabbitMQOutboxEvent
from messaging_lab.exceptions import (
    DuplicateProductsError,
    EmptyOrderError,
    InactiveProductsError,
    InsufficientProductStockError,
    OrderNotFoundError,
    ProductsNotFoundError,
)
from messaging_lab.integrations.catalog import CatalogClient
from messaging_lab.messaging.contracts.payments import PaymentRequestedV1
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.schemas.catalog import CatalogProductSnapshot


@dataclass(frozen=True, slots=True)
class CreateOrderItem:
    product_id: UUID
    quantity: int


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        order_repository: OrderRepository,
        catalog_client: CatalogClient,
        rabbitmq_outbox_repository: RabbitMQOutboxRepository,
        kafka_outbox_repository: KafkaOutboxRepository,
    ) -> None:
        self._session = session
        self._order_repository = order_repository
        self._catalog_client = catalog_client
        self._rabbitmq_outbox_repository = rabbitmq_outbox_repository
        self._kafka_outbox_repository = kafka_outbox_repository


    def _collect_product_ids(self, items: Sequence[CreateOrderItem]) -> set[UUID]:
        
        if not items:
            raise EmptyOrderError()
        
        product_ids: set[UUID] = set()
        duplicate_ids: set[UUID] = set()

        for item in items:
            if item.product_id in product_ids:
                duplicate_ids.add(item.product_id)
            product_ids.add(item.product_id)
        
        if duplicate_ids:
            raise DuplicateProductsError(duplicate_ids)
        
        return product_ids
    
    def _validate_and_index_products(
        self,
        requested_ids: set[UUID],
        products: Sequence[CatalogProductSnapshot],
    ) -> dict[UUID, CatalogProductSnapshot]:
        products_by_id: dict[UUID, CatalogProductSnapshot] = {}
        inactive_ids: set[UUID] = set()

        for product in products:
            products_by_id[product.id] = product

            if not product.is_active:
                inactive_ids.add(product.id)
        
        missing_ids = requested_ids - products_by_id.keys()
        if missing_ids:
            raise ProductsNotFoundError(missing_ids)
        
        if inactive_ids:
            raise InactiveProductsError(inactive_ids)
        
        return products_by_id

    def _validate_stock(
        self,
        items: Sequence[CreateOrderItem],
        products_by_id: dict[UUID, CatalogProductSnapshot],
    ) -> None:
        for item in items:
            product = products_by_id[item.product_id]
            if item.quantity > product.stock_quantity:
                raise InsufficientProductStockError(
                    product_id=product.id,
                    requested_quantity=item.quantity,
                    available_quantity=product.stock_quantity
                )


    def _build_order(
        self,
        customer_id: UUID,
        receipt_email: str,
        items: Sequence[CreateOrderItem],
        products_by_id: dict[UUID, CatalogProductSnapshot],
    ) -> Order:
        order_items: list[OrderItem] = []
        total_amount = Decimal("0")
        

        for item in items:
            product = products_by_id[item.product_id]
            new_order_item = OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=product.price
            )
            order_items.append(new_order_item)
            total_amount += product.price * item.quantity
        order = Order(
            customer_id=customer_id,
            receipt_email=receipt_email,
            total_amount=total_amount,
            items=order_items
        )
        return order

    def _build_order_created_notifications_event(self, order: Order) -> RabbitMQOutboxEvent:
        payload: dict[str, object] = {
            "order_id": str(order.id),
            "customer_id": str(order.customer_id),
            "receipt_email": order.receipt_email,
            "total_amount": str(order.total_amount),
            "items": [
                {
                    "product_id": str(item.product_id),
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                }
                for item in order.items
            ],
        }
        return RabbitMQOutboxEvent(
            aggregate_id=order.id,
            event_type="order.created",
            event_version=1,
            payload=payload,
        )

    def _build_payment_requested_event(self, order: Order) -> RabbitMQOutboxEvent:
        payment_requested = PaymentRequestedV1(
            order_id=order.id,
            amount=order.total_amount,
            currency="RUB",
        )
        payload = payment_requested.model_dump(mode="json")


        return RabbitMQOutboxEvent(
            aggregate_id=order.id,
            event_type="payment.requested",
            event_version=1,
            payload=payload
        )
    
    def _build_order_analytics_event(self, order: Order,) -> KafkaOutboxEvent:
        payload: dict[str, object] = {
            "order_id": str(order.id),
            "customer_id": str(order.customer_id),
            "total_amount": str(order.total_amount),
            "items": [
                {
                    "product_id": str(item.product_id),
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price)
                }
                for item in order.items
            ],
        }
        return KafkaOutboxEvent(
            aggregate_id=order.id,
            event_type="order.created",
            event_version=1,
            payload=payload,
        )

    async def create_order(
        self,
        customer_id: UUID,
        receipt_email: str,
        items: Sequence[CreateOrderItem],
    ) -> Order:
        product_ids = self._collect_product_ids(items)
        products = await self._catalog_client.get_products_by_ids(product_ids=product_ids)
        products_by_id = self._validate_and_index_products(
            requested_ids=product_ids,
            products=products,
        )
        self._validate_stock(items=items, products_by_id=products_by_id)
        async with self._session.begin():
            order = self._build_order(
                customer_id=customer_id,
                receipt_email=receipt_email,
                items=items,
                products_by_id=products_by_id,
            )
            created_order = await self._order_repository.add(order)
            payment_requested_event = self._build_payment_requested_event(created_order)
            kafka_event = self._build_order_analytics_event(created_order)
            await self._rabbitmq_outbox_repository.add(payment_requested_event)
            await self._kafka_outbox_repository.add(kafka_event)
        return created_order

    async def get_order(self, order_id: UUID) -> Order:
        async with self._session.begin():
            order = await self._order_repository.get_by_id(order_id)
            if order is None:
                raise OrderNotFoundError(order_id)
        return order

    async def get_orders_by_customer(
        self,
        customer_id: UUID,
        limit: int,
        offset: int,
    ) -> list[Order]:
        async with self._session.begin():
            orders = await self._order_repository.list_by_customer_id(
                customer_id=customer_id,
                limit=limit,
                offset=offset,
            )
        return orders
