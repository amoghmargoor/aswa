"""Configuration management for Agent Service."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service Configuration
    service_name: str = "agent-service"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8090
    workers: int = 4

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_agents"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis Configuration
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_prefix: str = "aswa:agents:"

    # Authentication
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Internal Service URLs (for K8s service discovery)
    insight_service_url: str = "http://insight-service:8080"
    query_service_url: str = "http://query-service:8080"
    integration_service_url: str = "http://integration-service:8080"
    notification_service_url: str = "http://notification-service:8080"
    api_gateway_url: str = "http://api-gateway:8080"

    # LLM Configuration
    llm_provider: Literal["anthropic", "openai", "bedrock", "azure"] = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    aws_region: str = "us-east-1"
    default_model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4096

    # Agent Execution
    max_concurrent_executions: int = 100
    execution_timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Approval Configuration
    default_approval_timeout_hours: int = 24
    high_risk_actions: list[str] = Field(
        default=["send_email", "create_ticket", "update_document", "call_webhook"]
    )

    # Observability
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    otlp_endpoint: str | None = None

    # Feature Flags
    enable_nlp_generation: bool = True
    enable_visual_builder: bool = True
    enable_marketplace: bool = False

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
