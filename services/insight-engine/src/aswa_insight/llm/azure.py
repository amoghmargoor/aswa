"""Azure OpenAI LLM client implementation."""

import time
from typing import Any, Type, TypeVar

import structlog
from pydantic import BaseModel

from aswa_insight.llm.client import LLMClient

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class AzureOpenAIClient(LLMClient):
    """Azure OpenAI LLM client.

    Uses the Azure OpenAI service with instructor for
    structured output extraction.
    """

    def __init__(
        self,
        endpoint: str | None,
        api_key: str | None,
        deployment: str = "gpt-4o",
        api_version: str = "2024-02-01",
        max_retries: int = 3,
        timeout: int = 120,
    ) -> None:
        """Initialize Azure OpenAI client.

        Args:
            endpoint: Azure OpenAI endpoint URL
            api_key: API key
            deployment: Deployment name
            api_version: API version
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self._endpoint = endpoint
        self._api_key = api_key
        self._deployment = deployment
        self._api_version = api_version
        self._max_retries = max_retries
        self._timeout = timeout

        self._client: Any = None
        self._instructor_client: Any = None

        # Metrics tracking
        self._request_count = 0
        self._error_count = 0
        self._total_tokens = 0

        if not endpoint or not api_key:
            logger.warning("Azure OpenAI credentials not configured")

    async def initialize(self) -> None:
        """Initialize Azure OpenAI client."""
        logger.info(
            "Azure OpenAI client initialized",
            endpoint=self._endpoint,
            deployment=self._deployment,
        )

    async def _get_client(self) -> Any:
        """Get or create Azure OpenAI client."""
        if self._client is None:
            from openai import AsyncAzureOpenAI

            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._endpoint,
                api_key=self._api_key,
                api_version=self._api_version,
                max_retries=self._max_retries,
                timeout=self._timeout,
            )

        return self._client

    async def _get_instructor_client(self) -> Any:
        """Get or create instructor-patched client."""
        if self._instructor_client is None:
            import instructor

            client = await self._get_client()
            self._instructor_client = instructor.from_openai(client)

        return self._instructor_client

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Generate text completion using Azure OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stop_sequences: Optional stop sequences

        Returns:
            Generated text completion
        """
        start_time = time.monotonic()
        client = await self._get_client()

        try:
            response = await client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop_sequences,
            )

            # Track metrics
            self._request_count += 1
            if response.usage:
                self._total_tokens += response.usage.total_tokens

            elapsed = time.monotonic() - start_time
            logger.debug(
                "Azure OpenAI completion successful",
                duration_ms=int(elapsed * 1000),
                tokens=response.usage.total_tokens if response.usage else 0,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Azure OpenAI completion failed",
                error=str(e),
                deployment=self._deployment,
            )
            raise

    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type[T],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> T:
        """Generate structured completion using instructor.

        Args:
            messages: List of message dicts
            response_model: Pydantic model for response validation
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            max_retries: Retries for validation failures

        Returns:
            Parsed and validated response
        """
        start_time = time.monotonic()
        client = await self._get_instructor_client()

        try:
            response = await client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_model=response_model,
                max_retries=max_retries,
            )

            self._request_count += 1
            elapsed = time.monotonic() - start_time

            logger.debug(
                "Azure OpenAI structured completion successful",
                duration_ms=int(elapsed * 1000),
                response_model=response_model.__name__,
            )

            return response

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Azure OpenAI structured extraction failed",
                error=str(e),
                model=response_model.__name__,
            )
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Uses tiktoken for accurate token counting.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        try:
            import tiktoken

            # GPT-4 uses cl100k_base encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to character-based approximation
            return len(text) // 4

    async def health_check(self) -> bool:
        """Check Azure OpenAI connectivity.

        Returns:
            True if healthy and reachable
        """
        try:
            response = await self.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                temperature=0.0,
            )
            return len(response) > 0
        except Exception as e:
            logger.warning("Azure OpenAI health check failed", error=str(e))
            return False

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "azure_openai"

    @property
    def model_id(self) -> str:
        """Get model/deployment ID."""
        return self._deployment

    def get_metrics(self) -> dict[str, Any]:
        """Get client metrics.

        Returns:
            Dict with request counts, errors, and token usage
        """
        return {
            "provider": self.provider_name,
            "model": self._deployment,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
        }

    async def close(self) -> None:
        """Close client connections."""
        if self._client is not None:
            await self._client.close()
            self._client = None

        logger.info("Azure OpenAI client closed")
