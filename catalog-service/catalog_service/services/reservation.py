
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.products import Product
from catalog_service.db.models.outbox import RabbitMQOutboxEvent
from catalog_service.db.models.reservation import StockReservation, StockReservationStatus
from catalog_service.db.models.reservation_items import StockReservationItem
from catalog_service.repositories.products import ProductRepository
from catalog_service.repositories.reservation import StockReservationRepository
from catalog_service.repositories.outbox import RabbitMQOutboxRepository
from catalog_service.repositories.inbox import InboxRepository

from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationFailureCode,
    StockReservationRequestedEnvelopeV1,
    StockReservedV1,
    StockReservationFailedV1,
)

@dataclass(frozen=True, slots=True)
class ReservationFailure:
    code: StockReservationFailureCode
    product_ids: set[UUID]

class StockReservationService:
    def __init__(
        self,
        session: AsyncSession,
        product_repository: ProductRepository,
        reservation_repository: StockReservationRepository,
        outbox_repository: RabbitMQOutboxRepository,
        inbox_repository: InboxRepository,
        consumer_name: str
    ) -> None:
        self._session = session
        self._product_repository = product_repository
        self._reservation_repository = reservation_repository
        self._outbox_repository = outbox_repository
        self._inbox_repository = inbox_repository
        self._consumer_name = consumer_name

    def _build_reserved_event(
        self,
        reservation: StockReservation
    ) -> RabbitMQOutboxEvent:

        payload = StockReservedV1(
            reservation_id=reservation.id,
            order_id=reservation.order_id,
            reserved_at=reservation.created_at
        )
        
        return RabbitMQOutboxEvent(
            aggregate_id=reservation.id,
            correlation_id=reservation.order_id,
            event_type="stock.reserved",
            event_version=1,
            payload=payload.model_dump(mode="json"),
        )

    def _build_failed_event(
        self,
        reservation: StockReservation,
        failure: ReservationFailure,
        failed_at: datetime,
    ) -> RabbitMQOutboxEvent:
        payload = StockReservationFailedV1(
            order_id=reservation.order_id,
            failure_code=failure.code,
            failed_product_ids=failure.product_ids,
            failed_at=failed_at,
        )

        return RabbitMQOutboxEvent(
            aggregate_id=reservation.id,
            correlation_id=reservation.order_id,
            event_type="stock.reservation.failed",
            event_version=1,
            payload=payload.model_dump(mode="json"),
        )

    def _find_reservation_failure(
        self,
        requested_quantities: dict[UUID, int],
        products_by_id: dict[UUID, Product],
    ) -> ReservationFailure | None:
        
        requested_ids = requested_quantities.keys()
        missing_ids =  requested_ids - products_by_id.keys()

        if missing_ids:
            return ReservationFailure(
                code="product_not_found",
                product_ids=missing_ids,
            )

        inactive_ids = {
            product_id
            for product_id, product in products_by_id.items()
            if not product.is_active
        }

        if inactive_ids:
            return ReservationFailure(
                code="product_inactive",
                product_ids=inactive_ids,
            )

        insufficient_ids = {
            product_id
            for product_id, requested_quantity in requested_quantities.items()
            if requested_quantity > products_by_id[product_id].stock_quantity
        }

        if insufficient_ids:
            return ReservationFailure(
                code="insufficient_stock",
                product_ids=insufficient_ids,
            )

        return None

    async def process(self, event: StockReservationRequestedEnvelopeV1) -> bool:
        async with self._session.begin():
            is_new = await self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type
            )

            if not is_new:
                return False

            existing_reservation = await self._reservation_repository.get_by_order_id(order_id=event.payload.order_id)
            if existing_reservation is not None:
                return False

            requested_quantities = {
                item.product_id: item.quantity
                for item in event.payload.items
            }

            product_ids = set(requested_quantities)

            products = await self._product_repository.get_by_ids_for_update(product_ids=product_ids)
            products_by_id = {
                product.id: product
                for product in products
            }

            failure = self._find_reservation_failure(
                requested_quantities=requested_quantities,
                products_by_id=products_by_id
            )

            if failure is not None:

                failed_at = datetime.now(UTC)

                reservation = StockReservation(
                    order_id=event.payload.order_id,
                    status=StockReservationStatus.FAILED,
                    failure_code=failure.code,
                    finalized_at=failed_at
                )

                await self._reservation_repository.add(reservation)

                failed_event = self._build_failed_event(
                    reservation=reservation,
                    failure=failure,
                    failed_at=failed_at
                )

                await self._outbox_repository.add(failed_event)
                return True

            for product_id, requested_quantity in requested_quantities.items():
                product = products_by_id[product_id]
                product.stock_quantity -= requested_quantity

            reservation = StockReservation(
                order_id=event.payload.order_id,
                status=StockReservationStatus.RESERVED,
                items=[
                    StockReservationItem(
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    for item in event.payload.items
                ],
            )

            await self._reservation_repository.add(reservation)

            reserved_event = self._build_reserved_event(reservation)
            await self._outbox_repository.add(reserved_event)

            return True
