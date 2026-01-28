from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Slack bot configuration."""

    # Slack credentials
    slack_bot_token: str = Field(..., description="Slack Bot User OAuth Token")
    slack_signing_secret: str = Field(..., description="Slack Signing Secret")
    slack_app_token: str = Field(default="", description="Slack App-Level Token for Socket Mode")

    # OAuth settings
    slack_client_id: str = Field(default="", description="Slack Client ID for OAuth")
    slack_client_secret: str = Field(default="", description="Slack Client Secret")
    slack_oauth_redirect_uri: str = Field(default="", description="OAuth Redirect URI")

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
    default_response_timeout: int = Field(default=30, description="Response timeout in seconds")
    max_results_per_message: int = Field(default=5, description="Max results to show")

    # Rate limiting
    rate_limit_per_user: int = Field(default=20, description="Requests per minute per user")
    rate_limit_per_workspace: int = Field(default=100, description="Requests per minute per workspace")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {"env_prefix": "ASWA_SLACK_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
