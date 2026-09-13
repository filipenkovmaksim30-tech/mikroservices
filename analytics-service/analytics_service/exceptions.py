from uuid import UUID

class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")

class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Administrator privileges required")


class InvalidAnalyticsPeriodError(Exception):
    """Analytics period is invalid."""


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Заказ с id={order_id} не найден")