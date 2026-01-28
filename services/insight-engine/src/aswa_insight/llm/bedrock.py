"""AWS Bedrock LLM client implementation."""

import json
import time
from typing import Any, Type, TypeVar

import aioboto3
import structlog
from botocore.config import Config
from pydantic import BaseModel

from aswa_insight.llm.client import LLMClient

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


class BedrockClient(LLMClient):
    """AWS Bedrock LLM client with Instructor support.

    Supports Claude models through the Bedrock runtime API.
    Uses instructor for structured output extraction.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        max_retries: int = 3,
        timeout: int = 120,
    ) -> None:
        """Initialize Bedrock client.

        Args:
            region: AWS region
            model_id: Bedrock model identifier
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
        """
        self._region = region
        self._model_id = model_id
        self._max_retries = max_retries
        self._timeout = timeout

        self._session: aioboto3.Session | None = None
        self._client: Any = None
        self._instructor_client: Any = None

        # Metrics tracking
        self._request_count = 0
        self._error_count = 0
        self._total_tokens = 0

    async def initialize(self) -> None:
        """Initialize boto3 session and client."""
        self._session = aioboto3.Session()
        logger.info(
            "Bedrock client initialized",
            region=self._region,
            model=self._model_id,
        )

    async def _get_client(self) -> Any:
        """Get or create Bedrock runtime client."""
        if self._client is None:
            if self._session is None:
                self._session = aioboto3.Session()

            config = Config(
                retries={"max_attempts": self._max_retries, "mode": "adaptive"},
                read_timeout=self._timeout,
                connect_timeout=30,
            )

            self._client = await self._session.client(
                "bedrock-runtime",
                region_name=self._region,
                config=config,
            ).__aenter__()

        return self._client

    async def _get_instructor_client(self) -> Any:
        """Get or create instructor-patched client."""
        if self._instructor_client is None:
            import instructor
            from anthropic import AsyncAnthropicBedrock

            # Create Anthropic Bedrock client
            anthropic_client = AsyncAnthropicBedrock(
                aws_region=self._region,
            )

            # Patch with instructor
            self._instructor_client = instructor.from_anthropic(anthropic_client)

        return self._instructor_client

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Generate text completion using Bedrock Claude.

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

        # Extract system message if present
        system_prompt = None
        conversation_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                conversation_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": conversation_messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        if stop_sequences:
            body["stop_sequences"] = stop_sequences

        try:
            response = await client.invoke_model(
                modelId=self._model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(await response["body"].read())
            content = response_body.get("content", [])

            # Track metrics
            self._request_count += 1
            usage = response_body.get("usage", {})
            self._total_tokens += usage.get("input_tokens", 0)
            self._total_tokens += usage.get("output_tokens", 0)

            elapsed = time.monotonic() - start_time
            logger.debug(
                "Bedrock completion successful",
                duration_ms=int(elapsed * 1000),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

            if content and isinstance(content, list):
                return content[0].get("text", "")
            return ""

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Bedrock completion failed",
                error=str(e),
                model=self._model_id,
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

        # Extract system message
        system_prompt = "You are a helpful assistant."
        conversation_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", system_prompt)
            else:
                conversation_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        try:
            response = await client.messages.create(
                model=self._model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=conversation_messages,
                response_model=response_model,
                max_retries=max_retries,
            )

            self._request_count += 1
            elapsed = time.monotonic() - start_time

            logger.debug(
                "Bedrock structured completion successful",
                duration_ms=int(elapsed * 1000),
                response_model=response_model.__name__,
            )

            return response

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Bedrock structured extraction failed",
                error=str(e),
                model=response_model.__name__,
            )
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Uses a simple approximation based on characters.
        For accurate counts, use the actual tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Claude uses roughly 4 characters per token on average
        # This is an approximation - for exact counts use anthropic tokenizer
        try:
            import tiktoken

            # Use cl100k_base as approximation for Claude
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to character-based approximation
            return len(text) // 4

    async def health_check(self) -> bool:
        """Check Bedrock connectivity.

        Returns:
            True if healthy and reachable
        """
        try:
            # Simple completion test
            response = await self.complete(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
                temperature=0.0,
            )
            return len(response) > 0
        except Exception as e:
            logger.warning("Bedrock health check failed", error=str(e))
            return False

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "bedrock"

    @property
    def model_id(self) -> str:
        """Get model ID."""
        return self._model_id

    def get_metrics(self) -> dict[str, Any]:
        """Get client metrics.

        Returns:
            Dict with request counts, errors, and token usage
        """
        return {
            "provider": self.provider_name,
            "model": self._model_id,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
        }

    async def close(self) -> None:
        """Close client connections."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

        logger.info("Bedrock client closed")
