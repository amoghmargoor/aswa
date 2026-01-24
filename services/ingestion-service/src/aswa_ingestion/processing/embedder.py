"""Embedding client for generating vector embeddings."""

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings

logger = get_logger(__name__)


class EmbeddingMetrics(BaseModel):
    """Metrics for embedding operations."""

    total_tokens: int = 0
    total_requests: int = 0
    total_latency_ms: float = 0
    failed_requests: int = 0


class EmbeddingClient:
    """Generate embeddings using AWS Bedrock or Azure OpenAI.

    Supports batching, rate limiting, and automatic retries
    with exponential backoff.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        """Initialize embedding client.

        Args:
            provider: Embedding provider (bedrock, azure, openai)
            model: Model identifier
            dimension: Embedding dimension
        """
        self.provider = provider or settings.embedding.provider
        self.model = model or settings.embedding.model
        self.dimension = dimension or settings.embedding.dimension

        # Clients initialized lazily
        self._bedrock_client: Any = None
        self._azure_client: Any = None
        self._openai_client: Any = None

        # Metrics
        self.metrics = EmbeddingMetrics()

        logger.info(
            f"EmbeddingClient initialized: provider={self.provider}, "
            f"model={self.model}, dimension={self.dimension}"
        )

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for single text.

        Args:
            text: Input text

        Returns:
            Embedding vector

        Raises:
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        results = await self.embed_batch([text], batch_size=1)
        return results[0]

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts with batching.

        Handles rate limiting with exponential backoff.
        Logs metrics for latency and token usage.

        Args:
            texts: List of input texts
            batch_size: Maximum texts per API call

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If texts list is empty
        """
        if not texts:
            return []

        # Filter empty texts and track indices
        valid_texts: list[tuple[int, str]] = [
            (i, t.strip()) for i, t in enumerate(texts) if t and t.strip()
        ]

        if not valid_texts:
            return [[0.0] * self.dimension for _ in texts]

        logger.debug(
            f"Embedding {len(valid_texts)} texts in batches of {batch_size}"
        )

        start_time = time.time()
        all_embeddings: dict[int, list[float]] = {}

        # Process in batches
        for batch_start in range(0, len(valid_texts), batch_size):
            batch_end = min(batch_start + batch_size, len(valid_texts))
            batch = valid_texts[batch_start:batch_end]
            batch_texts = [t[1] for t in batch]
            batch_indices = [t[0] for t in batch]

            # Retry with exponential backoff
            embeddings = await self._embed_with_retry(batch_texts)

            for idx, embedding in zip(batch_indices, embeddings):
                all_embeddings[idx] = embedding

            self.metrics.total_requests += 1

        # Build result maintaining original order
        result: list[list[float]] = []
        for i in range(len(texts)):
            if i in all_embeddings:
                result.append(all_embeddings[i])
            else:
                # Empty text - return zero vector
                result.append([0.0] * self.dimension)

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.total_latency_ms += elapsed_ms

        logger.info(
            f"Embedded {len(valid_texts)} texts in {elapsed_ms:.0f}ms "
            f"({elapsed_ms / len(valid_texts):.1f}ms/text)"
        )

        return result

    async def _embed_with_retry(
        self,
        texts: list[str],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> list[list[float]]:
        """Embed texts with retry logic.

        Args:
            texts: Texts to embed
            max_retries: Maximum retry attempts
            base_delay: Base delay for exponential backoff

        Returns:
            List of embeddings
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                if self.provider == "bedrock":
                    return await self._embed_bedrock(texts)
                elif self.provider == "azure":
                    return await self._embed_azure(texts)
                elif self.provider == "openai":
                    return await self._embed_openai(texts)
                else:
                    raise ValueError(f"Unknown provider: {self.provider}")

            except Exception as e:
                last_error = e
                self.metrics.failed_requests += 1

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Embedding failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Embedding failed after {max_retries} attempts: {e}")

        raise last_error or RuntimeError("Embedding failed")

    async def _embed_bedrock(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using AWS Bedrock.

        Args:
            texts: Texts to embed

        Returns:
            List of embeddings
        """
        if self._bedrock_client is None:
            import aioboto3

            session = aioboto3.Session()
            self._bedrock_client = await session.client(
                "bedrock-runtime",
                region_name=settings.embedding.aws_region,
            ).__aenter__()

        # Bedrock Titan embeddings
        embeddings: list[list[float]] = []

        for text in texts:
            import json

            body = json.dumps({"inputText": text})

            response = await self._bedrock_client.invoke_model(
                modelId=self.model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(await response["body"].read())
            embedding = response_body.get("embedding", [])

            # Estimate token count
            self.metrics.total_tokens += len(text.split())

            embeddings.append(embedding)

        return embeddings

    async def _embed_azure(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Azure OpenAI.

        Args:
            texts: Texts to embed

        Returns:
            List of embeddings
        """
        if self._azure_client is None:
            from openai import AsyncAzureOpenAI

            self._azure_client = AsyncAzureOpenAI(
                api_key=settings.embedding.azure_api_key,
                api_version=settings.embedding.azure_api_version,
                azure_endpoint=settings.embedding.azure_endpoint,
            )

        response = await self._azure_client.embeddings.create(
            model=self.model,
            input=texts,
        )

        embeddings = [data.embedding for data in response.data]

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.metrics.total_tokens += response.usage.total_tokens

        return embeddings

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI.

        Args:
            texts: Texts to embed

        Returns:
            List of embeddings
        """
        if self._openai_client is None:
            from openai import AsyncOpenAI

            self._openai_client = AsyncOpenAI(
                api_key=settings.embedding.openai_api_key,
            )

        response = await self._openai_client.embeddings.create(
            model=self.model,
            input=texts,
        )

        embeddings = [data.embedding for data in response.data]

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.metrics.total_tokens += response.usage.total_tokens

        return embeddings

    async def close(self) -> None:
        """Close any open clients."""
        if self._bedrock_client is not None:
            await self._bedrock_client.__aexit__(None, None, None)
            self._bedrock_client = None

        if self._azure_client is not None:
            await self._azure_client.close()
            self._azure_client = None

        if self._openai_client is not None:
            await self._openai_client.close()
            self._openai_client = None
