# Task 3.1.2: LLM Client Abstraction (Bedrock & Azure)

## Subtask: Create LLM Client with Bedrock and Azure OpenAI Support

**Claude Code Prompt:**
```
Create the LLM client abstraction at /services/insight-engine/src/aswa_insight/llm/.

1. /services/insight-engine/src/aswa_insight/llm/client.py:
from abc import ABC, abstractmethod
from typing import TypeVar, Type, Any
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None
    ) -> str:
        """Generate a text completion."""
        ...
    
    @abstractmethod
    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        max_retries: int = 3
    ) -> T:
        """Generate a structured completion with Pydantic validation."""
        ...
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Close client resources."""
        ...

async def get_llm_client() -> LLMClient:
    """Factory function to create appropriate LLM client."""
    from ..config import settings
    
    if settings.insight.llm_provider == "bedrock":
        from .bedrock import BedrockClient
        client = BedrockClient(
            region=settings.insight.bedrock_region,
            model_id=settings.insight.bedrock_model_id
        )
    elif settings.insight.llm_provider == "azure_openai":
        from .azure import AzureOpenAIClient
        client = AzureOpenAIClient(
            endpoint=settings.insight.azure_endpoint,
            api_key=settings.insight.azure_api_key,
            deployment=settings.insight.azure_deployment,
            api_version=settings.insight.azure_api_version
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.insight.llm_provider}")
    
    await client.initialize()
    return client

2. /services/insight-engine/src/aswa_insight/llm/bedrock.py:
import aioboto3
from botocore.config import Config
import json
from typing import Type, TypeVar
from pydantic import BaseModel
import instructor
from instructor.patch import patch
import structlog
from aswa_common.resilience import retry_with_backoff
from aswa_common.metrics import MetricsRegistry
from .client import LLMClient

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

class BedrockClient(LLMClient):
    """AWS Bedrock LLM client with Instructor support."""
    
    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_retries: int = 3,
        timeout: int = 120
    ):
        self.region = region
        self.model_id = model_id
        self.max_retries = max_retries
        self.timeout = timeout
        
        self._session: aioboto3.Session | None = None
        self._metrics = MetricsRegistry("bedrock_llm")
        
        # Metrics
        self._request_counter = self._metrics.counter(
            "requests_total", "Total LLM requests", ["status"]
        )
        self._latency_histogram = self._metrics.histogram(
            "request_duration_seconds", "LLM request duration"
        )
        self._token_counter = self._metrics.counter(
            "tokens_total", "Total tokens used", ["type"]
        )
    
    async def initialize(self) -> None:
        """Initialize boto3 session."""
        self._session = aioboto3.Session()
        logger.info("Bedrock client initialized", region=self.region, model=self.model_id)
    
    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None
    ) -> str:
        """Generate completion using Bedrock."""
        import time
        start = time.monotonic()
        
        config = Config(
            retries={"max_attempts": self.max_retries, "mode": "adaptive"},
            read_timeout=self.timeout,
            connect_timeout=30
        )
        
        try: