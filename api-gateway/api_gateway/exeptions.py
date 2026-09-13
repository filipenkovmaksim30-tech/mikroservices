class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")


class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Administrator privileges required")