from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Query service configuration."""

    # Service
    service_name: str = "query-service"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8003
    workers: int = 4

    # API
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True

    # Redis Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600

    # Vector Store (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    # Insight Engine
    insight_engine_url: str = "http://localhost:8002"

    # LLM Settings
    llm_provider: str = "bedrock"  # bedrock, azure, openai
    llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1

    # Query Settings
    max_context_chunks: int = 10
    min_relevance_score: float = 0.7
    max_query_length: int = 1000

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: list[str] = ["*"]

    class Config:
        env_prefix = "QUERY_"
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
