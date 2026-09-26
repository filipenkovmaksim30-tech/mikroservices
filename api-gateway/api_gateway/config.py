from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
    env_file=".env",
    env_prefix="GATEWAY_",
    extra="ignore",
)

    catalog_base_url: str
    auth_base_url: str
    orders_base_url: str
    analytics_base_url: str
    payment_base_url: str
    refresh_cookie_name: str = Field(default="refresh_token", min_length=1)

    jwt_public_key_path: Path
    jwt_algorithm: Literal["RS256"] = "RS256"
    jwt_issuer: str = Field(min_length=1, default="auth-service")
    jwt_audience: str = Field(min_length=1, default="orderflow-services")

    http_connect_timeout: float = Field(default=3.00, gt=0)
    http_read_timeout: float = Field(default=10.00, gt=0)
    http_write_timeout: float = Field(default=10.00, gt=0)
    http_pool_timeout: float = Field(default=3.00, gt=0)

    http_max_connections: int = Field(default=100, gt=0)
    keepalive_connections: int = Field(default=20, ge=0)

