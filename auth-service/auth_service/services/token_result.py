from dataclasses import dataclass
from datetime import datetime

from auth_service.schemas.tokens import TokenResponse


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    token_response: TokenResponse
    refresh_token: str
    refresh_token_expires_at: datetime