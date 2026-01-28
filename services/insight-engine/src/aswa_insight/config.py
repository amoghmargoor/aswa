"""Configuration for the insight engine service."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InsightSettings(BaseSettings):
    """Insight engine configuration."""

    model_config = SettingsConfigDict(env_prefix="INSIGHT_")

    service_name: str = "aswa-insight-engine"
    service_port: int = 8083
    debug: bool = False
    log_level: str = "INFO"

    # LLM Configuration
    llm_provider: Literal["bedrock", "azure_openai", "openai"] = "bedrock"

    # AWS Bedrock settings
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    # Azure OpenAI settings
    azure_endpoint: str | None = None
    azure_api_key: str | None = None
    azure_deployment: str = "gpt-4o"
    azure_api_version: str = "2024-02-01"

    # OpenAI settings
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_organization: str | None = None

    # Extraction settings
    max_tokens: int = 4096
    temperature: float = 0.0
    extraction_timeout_seconds: int = 120
    max_retries: int = 3

    # Batch settings
    batch_size: int = 10
    concurrent_extractions: int = 5

    # Confidence thresholds
    min_entity_confidence: float = 0.6
    min_insight_confidence: float = 0.5

    # Extraction types
    enabled_extraction_types: list[str] = Field(
        default=["entities", "risks", "opportunities", "patterns"]
    )


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "aswa"
    user: str = "aswa"
    password: str = "aswa_dev_password"
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def async_url(self) -> str:
        """Get async database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = "aswa_dev_password"
    db: int = 0

    @property
    def url(self) -> str:
        """Get Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class Settings:
    """Application settings container."""

    insight: InsightSettings = InsightSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()


settings = Settings()
