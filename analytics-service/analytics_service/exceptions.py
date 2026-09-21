from uuid import UUID


class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")

class PermanentAnalyticsEventError(Exception):
    "Permanent Analytics event error"

class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Administrator privileges required")


class InvalidAnalyticsPeriodError(Exception):
    """Analytics period is invalid."""


class OrderNotFoundError(Exception):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"Заказ с id={order_id} не найден")


class AnalyticsOrderDataMismatchError(PermanentAnalyticsEventError):
    def __init__(self, order_id: UUID, field: str) -> None:
        super().__init__(f"Analytics order {order_id}: {field} does not match the payment event")


class ConflictingAnalyticsPaymentResultError(PermanentAnalyticsEventError):
    def __init__(self, order_id: UUID) -> None:
        super().__init__(f"Analytics order {order_id} already has a different payment result")
