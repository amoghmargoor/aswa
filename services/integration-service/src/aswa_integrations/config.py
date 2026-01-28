from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Integration service settings."""

    # Service
    service_name: str = "aswa-integrations"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8004

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_integrations"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/3"

    # Encryption
    encryption_key: str = Field(
        default="change-me-in-production-32-chars!"
    )

    # Rate limiting
    default_rate_limit: int = 100  # requests per minute
    rate_limit_window: int = 60  # seconds

    # Health check
    health_check_interval: int = 60  # seconds
    health_check_timeout: int = 10  # seconds

    # API Gateway
    api_gateway_url: str = "http://localhost:8000"

    model_config = {
        "env_prefix": "INTEGRATIONS_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
