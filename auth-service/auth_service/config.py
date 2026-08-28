from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
    )

    postgresql_host: str
    postgresql_port: int = Field(gt=0, le=65535)
    postgresql_user: str = Field(min_length=1)
    postgresql_password: SecretStr
    postgresql_db: str = Field(min_length=1)

    jwt_private_key_path: Path
    jwt_public_key_path: Path
    jwt_algorithm: Literal["RS256"] = "RS256"
    jwt_access_token_expire_minutes: int = Field(default=15, gt=0, le=60)
    jwt_issuer: str = Field(default="auth-service", min_length=1)
    jwt_audience: str = Field(default="orderflow-services", min_length=1)

    refresh_token_expire_days: int = Field(default=30, gt=0, le=90)
    refresh_cookie_name: str = Field(default="refresh_token", min_length=1)
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @property
    def postgresql_url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgresql_user,
            password=self.postgresql_password.get_secret_value(),
            host=self.postgresql_host,
            port=self.postgresql_port,
            database=self.postgresql_db,
        )