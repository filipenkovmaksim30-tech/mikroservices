
class EmailAlreadyRegisteredError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__(f"User with email={email} already exists")


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class UserBlockedError(Exception):
     def __init__(self) -> None:
        super().__init__("User is blocked")

class InvalidAccessTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid access token")

class InvalidRefreshTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid refresh token")


class RefreshTokenReuseError(InvalidRefreshTokenError):
    """An already revoked refresh token was presented again."""


class PermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Insufficient permissions")
