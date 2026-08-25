from functools import lru_cache

from auth_service.config import Settings
from auth_service.security.tokens import TokenService

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    settings = get_settings()

    private_key = settings.jwt_private_key_path.read_text(encoding="utf-8")
    public_key = settings.jwt_public_key_path.read_text(encoding="utf-8")


    return TokenService(
        private_key=private_key,
        public_key=public_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience
    )