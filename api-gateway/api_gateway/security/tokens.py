import jwt
from pydantic import ValidationError

from api_gateway.exceptions import InvalidAccessTokenError
from api_gateway.schemas.tokens import AccessTokenPayload


class TokenVerifier:
    def __init__(
        self,
        public_key: str,
        algorithm: str,
        issuer: str,
        audience: str
    ) -> None:
        self._public_key = public_key
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

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

        except (ValidationError, jwt.InvalidTokenError) as exc:
            raise InvalidAccessTokenError() from exc
