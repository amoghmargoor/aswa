"""Configuration settings for the connector service."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "aswa"
    user: str = "aswa"
    password: str = "aswa"
    pool_size: int = 10
    pool_overflow: int = 20

    @property
    def url(self) -> str:
        """Get async database URL."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None

    @property
    def url(self) -> str:
        """Get Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class AirbyteSettings(BaseSettings):
    """Airbyte connection settings."""

    model_config = SettingsConfigDict(env_prefix="AIRBYTE_")

    # Airbyte API
    api_url: str = "http://localhost:8006"
    api_key: str | None = None

    # Workspace
    workspace_id: str | None = None
    workspace_name: str = "aswa-workspace"

    # Destination (webhook to receive data)
    destination_webhook_url: str = "http://connector-service:8000/internal/airbyte/records"

    # Sync settings
    sync_timeout_minutes: int = 60
    max_concurrent_syncs: int = 10


class OAuthSettings(BaseSettings):
    """OAuth provider settings."""

    model_config = SettingsConfigDict(env_prefix="OAUTH_")

    # Encryption key for storing tokens
    encryption_key: str = Field(
        default="dev-encryption-key-change-in-prod-32b",
        description="32-byte encryption key for OAuth tokens",
    )

    # Base redirect URI
    redirect_base_url: str = "http://localhost:8000"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Slack OAuth
    slack_client_id: str = ""
    slack_client_secret: str = ""

    # Salesforce OAuth
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_domain: str = "login.salesforce.com"


class ConnectorSettings(BaseSettings):
    """Connector service settings."""

    model_config = SettingsConfigDict(env_prefix="CONNECTOR_")

    # Provider selection
    default_provider: Literal["airbyte", "custom"] = "airbyte"

    # Ingestion service
    ingestion_service_url: str = "http://ingestion-service:8000"

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 5


class Settings(BaseSettings):
    """Main settings container."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service info
    service_name: str = "aswa-connector"
    version: str = "0.1.0"
    debug: bool = False

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    airbyte: AirbyteSettings = Field(default_factory=AirbyteSettings)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)
    connector: ConnectorSettings = Field(default_factory=ConnectorSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
