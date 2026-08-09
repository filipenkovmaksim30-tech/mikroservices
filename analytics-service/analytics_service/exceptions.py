from uuid import UUID


class InvalidAnalyticsPeriodError(Exception):
    """Analytics period is invalid."""


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Заказ с id={order_id} не найден")