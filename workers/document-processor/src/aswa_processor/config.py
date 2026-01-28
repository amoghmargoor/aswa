"""Configuration for the document processor worker."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Worker configuration."""

    model_config = SettingsConfigDict(env_prefix="WORKER_")

    # Worker config
    worker_name: str = "document-processor"
    concurrency: int = 4
    batch_size: int = 10
    poll_interval_seconds: int = 5
    max_retries: int = 3
    retry_delay_seconds: int = 60

    # Queue config
    queue_name: str = "document_processing"
    dead_letter_queue: str = "document_processing_dlq"
    visibility_timeout_seconds: int = 300

    # Processing limits
    max_document_size_mb: int = 50
    processing_timeout_seconds: int = 300


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = "aswa_dev_password"
    db: int = 0
    max_connections: int = 10

    @property
    def url(self) -> str:
        """Get Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "aswa"
    user: str = "aswa"
    password: str = "aswa_dev_password"
    pool_size: int = 5

    @property
    def async_url(self) -> str:
        """Get async database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


settings = WorkerSettings()
redis_settings = RedisSettings()
database_settings = DatabaseSettings()
