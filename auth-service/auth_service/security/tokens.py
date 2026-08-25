from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pydantic import ValidationError

from auth_service.db.models.users import UserRole
from auth_service.exceptions import InvalidAccessTokenError
from auth_service.schemas.tokens import AccessTokenPayload


class TokenService:
    def __init__(
        self,
        private_key: str,
        public_key: str,
        algorithm: str,
        access_token_expire_minutes: int,
        issuer: str,
        audience: str,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes
        self._issuer = issuer
        self._audience = audience

    def create_access_token(self, user_id: UUID, role: UserRole) -> str:

        now = datetime.now(UTC)

        expires_at = now + timedelta(minutes=self._access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid4()),
            "iss": self._issuer,
            "aud": self._audience
        }

        return jwt.encode(
            payload,
            self._private_key,
            algorithm=self._algorithm
        )

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": [
                        "sub",
                        "role",
                        "iat",
                        "exp",
                        "jti",
                        "iss",
                        "aud",
                    ]
                },
            )

            return AccessTokenPayload.model_validate(payload)

        except (jwt.InvalidTokenError, ValidationError) as exc:
            raise InvalidAccessTokenError() from exc


    