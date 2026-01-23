"""Configuration and settings management."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """Base application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "aswa"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False
    log_level: str = "INFO"


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "aswa"
    user: str = "aswa"
    password: SecretStr
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    @property
    def async_url(self) -> str:
        """Get async database URL for SQLAlchemy.

        Returns:
            PostgreSQL async URL
        """
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: SecretStr | None = None
    db: int = 0
    max_connections: int = 10

    @property
    def url(self) -> str:
        """Get Redis URL.

        Returns:
            Redis connection URL
        """
        if self.password:
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class LLMSettings(BaseSettings):
    """LLM provider settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: Literal["bedrock", "azure_openai"] = "bedrock"
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    aws_region: str = "us-east-1"
    azure_endpoint: str | None = None
    azure_api_key: SecretStr | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
