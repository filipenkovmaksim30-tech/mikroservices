from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_service.config import Settings
from analytics_service.security.tokens import TokenVerifier
from analytics_service.schemas.tokens import AccessTokenPayload
from analytics_service.services.analytics_orders import AnalyticsOrderService
from analytics_service.repositories.analytics_order import AnalyticsOrderRepository
from analytics_service.db.session import get_session
from analytics_service.exceptions import InvalidAccessTokenError, PermissionDeniedError

bearer_scheme = HTTPBearer(auto_error=False)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    return settings

@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifier:

    settings = get_settings()
    public_key = settings.jwt_public_key_path.read_text(encoding="utf-8")

    return TokenVerifier(
        public_key=public_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )

CredentialDependency = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
TokenVerifierDependency = Annotated[TokenVerifier, Depends(get_token_verifier)]

def get_current_principal(
    credentials: CredentialDependency,
    token_verifier: TokenVerifierDependency,
) -> AccessTokenPayload:
    if credentials is None:
        raise InvalidAccessTokenError
    return token_verifier.decode_access_token(credentials.credentials)

CurrentPrincipalDepends = Annotated[AccessTokenPayload, Depends(get_current_principal)]

def require_admin(
    current_admin: CurrentPrincipalDepends
) -> None:
    if current_admin.role != "admin":
        raise PermissionDeniedError
    


def get_analytics_service(
    session: Annotated[AsyncSession, Depends(get_session)]
):
    analytics_repository = AnalyticsOrderRepository(session)
    analytics_service = AnalyticsOrderService(analytics_repository, session)
    return analytics_service