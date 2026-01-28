from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Teams bot configuration."""

    # Bot Framework credentials
    app_id: str = Field(..., description="Microsoft App ID")
    app_password: str = Field(..., description="Microsoft App Password")

    # Service URLs
    query_service_url: str = Field(
        default="http://query-service:8000",
        description="Query service URL"
    )

    # Redis for state management
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis URL"
    )

    # Bot settings
    bot_name: str = Field(default="ASWA", description="Bot display name")
    default_response_timeout: int = Field(default=30, description="Response timeout")
    max_results_per_message: int = Field(default=5, description="Max results")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=3978, description="Server port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {"env_prefix": "ASWA_TEAMS_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
