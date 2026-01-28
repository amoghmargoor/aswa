from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Notification service settings."""

    # Service
    service_name: str = "aswa-notifications"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8005

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_notifications"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/4"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "noreply@aswa.io"
    email_from_name: str = "ASWA"

    # Push notifications
    firebase_credentials_path: str = ""
    apns_key_path: str = ""
    apns_key_id: str = ""
    apns_team_id: str = ""

    # Templates
    template_dir: str = "templates"

    # Rate limiting
    rate_limit_per_user: int = 100  # per hour
    rate_limit_per_tenant: int = 1000  # per hour

    model_config = {
        "env_prefix": "NOTIFICATIONS_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
