"""Abstract LLM client and factory."""

from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract base class for LLM clients.

    All LLM providers must implement this interface for
    consistent usage across the application.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Generate a text completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            stop_sequences: Optional sequences to stop generation

        Returns:
            Generated text completion
        """
        ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> T:
        """Generate a structured completion with Pydantic validation.

        Uses instructor library for structured output extraction.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            response_model: Pydantic model class for response validation
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            max_retries: Number of retries for validation failures

        Returns:
            Parsed response matching the Pydantic model
        """
        ...

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close client resources and connections."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize client resources.

        Called after construction to set up async resources.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Get model identifier."""
        ...

    async def health_check(self) -> bool:
        """Check if LLM service is healthy.

        Returns:
            True if healthy and reachable
        """
        try:
            response = await self.complete(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10,
                temperature=0.0,
            )
            return len(response) > 0
        except Exception as e:
            logger.warning("LLM health check failed", error=str(e))
            return False


async def get_llm_client() -> LLMClient:
    """Factory function to create LLM client based on configuration.

    Returns:
        Configured and initialized LLM client instance

    Raises:
        ValueError: If unknown provider is configured
    """
    from ..config import settings

    provider = settings.insight.llm_provider
    logger.info("Creating LLM client", provider=provider)

    if provider == "bedrock":
        from aswa_insight.llm.bedrock import BedrockClient

        client = BedrockClient(
            region=settings.insight.bedrock_region,
            model_id=settings.insight.bedrock_model_id,
        )
    elif provider == "azure_openai":
        from aswa_insight.llm.azure import AzureOpenAIClient

        client = AzureOpenAIClient(
            endpoint=settings.insight.azure_endpoint,
            api_key=settings.insight.azure_api_key,
            deployment=settings.insight.azure_deployment,
            api_version=settings.insight.azure_api_version,
        )
    elif provider == "openai":
        from aswa_insight.llm.openai_client import OpenAIClient

        client = OpenAIClient(
            api_key=settings.insight.openai_api_key,
            model=settings.insight.openai_model,
            organization=settings.insight.openai_organization,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    await client.initialize()

    logger.info(
        "LLM client created and initialized",
        provider=provider,
        model=client.model_id,
    )

    return client
