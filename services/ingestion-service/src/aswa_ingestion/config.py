"""Configuration for the ingestion service."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    def url(self) -> str:
        """Get async database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


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


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    collection: str = "documents"
    api_key: str | None = None
    prefer_grpc: bool = True


class EmbeddingSettings(BaseSettings):
    """Embedding configuration."""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    provider: Literal["openai", "bedrock", "local"] = "openai"
    model: str = "text-embedding-3-small"
    dimension: int = 1536
    batch_size: int = 100
    max_retries: int = 3

    # OpenAI
    openai_api_key: str | None = None

    # AWS Bedrock
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.titan-embed-text-v1"


class StorageSettings(BaseSettings):
    """Blob storage configuration."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_")

    type: Literal["local", "s3"] = "local"
    local_path: str = "/data/blobs"
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_prefix: str = "documents/"


class IngestionSettings(BaseSettings):
    """Ingestion service configuration."""

    model_config = SettingsConfigDict(env_prefix="INGESTION_")

    # Service
    service_name: str = "aswa-ingestion"
    service_port: int = 8081
    debug: bool = False
    log_level: str = "INFO"

    # Workers
    worker_concurrency: int = 4
    batch_size: int = 50
    max_retries: int = 3
    retry_delay_seconds: int = 60

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_chunks_per_doc: int = 100

    # Processing
    max_file_size_mb: int = 50
    supported_content_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/html",
            "application/json",
        ]
    )

    # Sync
    default_sync_interval_minutes: int = 60
    sync_job_timeout_minutes: int = 120


class Settings:
    """Application settings container."""

    ingestion: IngestionSettings = IngestionSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    qdrant: QdrantSettings = QdrantSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    storage: StorageSettings = StorageSettings()


settings = Settings()
