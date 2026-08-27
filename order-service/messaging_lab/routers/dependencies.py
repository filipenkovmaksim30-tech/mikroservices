from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.ext.asyncio import AsyncSession

from messaging_lab.db.session import get_session
from messaging_lab.repositories.orders import OrderRepository
from messaging_lab.repositories.rabbitmq_outbox import RabbitMQOutboxRepository
from messaging_lab.repositories.kafka_outbox import KafkaOutboxRepository
from messaging_lab.repositories.products import ProductRepository
from messaging_lab.services.orders import OrderService
from messaging_lab.config import Settings
from messaging_lab.exceptions import InvalidAccessTokenError, PermissionDeniedError
from messaging_lab.schemas.tokens import AccessTokenPayload
from messaging_lab.security.tokens import TokenVerifier

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
        audience=settings.jwt_audience,
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
def get_order_service(session: SessionDependency) -> OrderService:
    return OrderService(
        session=session,
        order_repository=OrderRepository(session),
        product_repository=ProductRepository(session),
        rabbitmq_outbox_repository=RabbitMQOutboxRepository(session),
        kafka_outbox_repository=KafkaOutboxRepository(session)
    )


OrderServiceDependency = Annotated[OrderService, Depends(get_order_service)]
