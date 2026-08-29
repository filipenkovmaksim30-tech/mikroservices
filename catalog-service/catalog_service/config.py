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
        case_sensitive=False
    )

    postgresql_host: str
    postgresql_port: int = Field(gt=0, le=65535)
    postgresql_user: str = Field(min_length=1)
    postgresql_password: SecretStr
    postgresql_db: str = Field(min_length=1)

    jwt_public_key_path: Path
    jwt_algorithm: Literal["RS256"] = "RS256"
    jwt_issuer: str = Field(min_length=1, default="auth-service")
    jwt_audience: str = Field(min_length=1, default="orderflow-services")

    @property
    def postgresql_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgresql_user,
            password=self.postgresql_password.get_secret_value(),
            host=self.postgresql_host,
            port=self.postgresql_port,
            database=self.postgresql_db
        )

