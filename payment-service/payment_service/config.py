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

    rabbitmq_host: str
    rabbitmq_port: int = Field(gt=0, le=65535)
    rabbitmq_user: str = Field(min_length=1)
    rabbitmq_password: SecretStr
    rabbitmq_vhost: str = Field(min_length=1)

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
    
    @property
    def rabbitmq_url(self) -> str:
        password = self.rabbitmq_password.get_secret_value()
    
        return (
            f"amqp://{self.rabbitmq_user}:{password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}"
            f"{self.rabbitmq_vhost}"
        )