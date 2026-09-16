from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from catalog_service.db.models.reservation import StockReservationStatus
from catalog_service.exceptions import (
    InvalidReservationStatusError,
    ReservationNotFoundError,
    ReservationProductsMissingError,
)
from catalog_service.messaging.contracts.stock_reservations import (
    StockReservationConfirmRequestedEnvelopeV1,
    StockReservationFinalizationEnvelopeV1,
    StockReservationReleaseRequestedEnvelopeV1,
)
from catalog_service.repositories.inbox import InboxRepository
from catalog_service.repositories.products import ProductRepository
from catalog_service.repositories.reservation import StockReservationRepository


class StockReservationFinalizationService:
    def __init__(
        self,
        session: AsyncSession,
        inbox_repository: InboxRepository,
        reservation_repository: StockReservationRepository,
        product_repository: ProductRepository,
        consumer_name: str,
    ) -> None:
        self._session = session
        self._inbox_repository = inbox_repository
        self._reservation_repository = reservation_repository
        self._product_repository = product_repository
        self._consumer_name = consumer_name

    async def process(self, event: StockReservationFinalizationEnvelopeV1) -> bool:

        async with self._session.begin():
            is_new = await self._inbox_repository.try_add(
                consumer_name=self._consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
            )

            if not is_new:
                return False

            reservation = await self._reservation_repository.get_by_order_id_for_update(
                event.payload.order_id
            )
            if reservation is None:
                raise ReservationNotFoundError(event.payload.order_id)

            if isinstance(event, StockReservationConfirmRequestedEnvelopeV1):
                if reservation.status is StockReservationStatus.CONFIRMED:
                    return False

                if reservation.status is not StockReservationStatus.RESERVED:
                    raise InvalidReservationStatusError(
                        order_id=reservation.order_id,
                        current_status=reservation.status,
                        target_status=StockReservationStatus.CONFIRMED,
                    )

                await self._reservation_repository.mark_confirmed(
                    reservation, finalized_at=datetime.now(UTC)
                )
                return True

            elif isinstance(event, StockReservationReleaseRequestedEnvelopeV1):
                if reservation.status is StockReservationStatus.RELEASED:
                    return False

                if reservation.status is not StockReservationStatus.RESERVED:
                    raise InvalidReservationStatusError(
                        order_id=reservation.order_id,
                        current_status=reservation.status,
                        target_status=StockReservationStatus.RELEASED,
                    )

                product_ids = {item.product_id for item in reservation.items}

                products = await self._product_repository.get_by_ids_for_update(product_ids)

                products_by_id = {product.id: product for product in products}

                missing_product_ids = product_ids - products_by_id.keys()
                if missing_product_ids:
                    raise ReservationProductsMissingError(
                        order_id=reservation.order_id,
                        product_ids=missing_product_ids,
                    )

                for item in reservation.items:
                    product = products_by_id[item.product_id]
                    product.stock_quantity += item.quantity

                await self._reservation_repository.mark_released(
                    reservation, finalized_at=datetime.now(UTC)
                )
                return True

            raise TypeError(f"Unsupported reservation finalization event: {type(event).__name__}")
