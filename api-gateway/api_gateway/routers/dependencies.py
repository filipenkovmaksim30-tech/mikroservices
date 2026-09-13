import httpx
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm

from api_gateway.config import Settings
from api_gateway.schemas.tokens import AccessTokenPayload
from api_gateway.security.tokens import TokenVerifier
from api_gateway.exeptions import InvalidAccessTokenError, PermissionDeniedError

bearer_scheme = HTTPBearer(auto_error=False)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

SettingsDependency = Annotated[Settings, Depends(get_settings)]

def get_http_client(request: Request) -> httpx.AsyncClient:

    return request.app.state.http_client


HttpClientDependency = Annotated[httpx.AsyncClient, Depends(get_http_client)]

@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    public_key = settings.jwt_public_key_path.read_text(encoding="utf-8")

    return TokenVerifier(
        public_key=public_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience
    )

CredentialsDependency = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
TokenVerifierDependency = Annotated[TokenVerifier, Depends(get_token_verifier)]

def get_current_principal(
    credentials: CredentialsDependency,
    token_verifier: TokenVerifierDependency
) -> AccessTokenPayload:
    if credentials is None:
        raise InvalidAccessTokenError()

    return token_verifier.decode_access_token(credentials.credentials)

CurrentPrincipalDependency = Annotated[AccessTokenPayload, Depends(get_current_principal)]

def require_admine(
    current_admin: CurrentPrincipalDependency
) -> None:
    if current_admin.role != "admin":
        raise PermissionDeniedError()

LoginFormDependency = Annotated[OAuth2PasswordRequestForm, Depends()]
    