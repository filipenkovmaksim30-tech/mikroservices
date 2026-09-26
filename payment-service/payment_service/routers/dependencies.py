from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from payment_service.config import Settings
from payment_service.db.session import get_session
from payment_service.exceptions import InvalidAccessTokenError, PermissionDeniedError
from payment_service.repositories.payments import PaymentRepository
from payment_service.schemas.tokens import AccessTokenPayload
from payment_service.security.tokens import TokenVerifier
from payment_service.services.payment import PaymentService

bearer_scheme = HTTPBearer(auto_error=False)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

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
    token_verifier: TokenVerifierDependency,
) -> AccessTokenPayload:
    if credentials is None:
        raise InvalidAccessTokenError()
    return token_verifier.decode_access_token(credentials.credentials)

CurrentPrincipalDependency = Annotated[AccessTokenPayload, Depends(get_current_principal)]

def require_admin(
   current_customer: CurrentPrincipalDependency 
) -> None:
    if current_customer.role != "admin":
        raise PermissionDeniedError()

SessionDependency = Annotated[AsyncSession, Depends(get_session)]

def get_payment_service(session: SessionDependency) -> PaymentService:
    return PaymentService(
        session=session,
        payment_repository=PaymentRepository(session)
    )

ServiceDependency = Annotated[PaymentService, Depends(get_payment_service)]
