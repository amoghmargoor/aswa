"""Tests for embedding client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_ingestion.processing.embedder import EmbeddingClient, EmbeddingMetrics


class TestEmbeddingClient:
    """Tests for EmbeddingClient class."""

    @pytest.fixture
    def client(self) -> EmbeddingClient:
        """Create embedding client instance."""
        return EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

    def test_init(self, client: EmbeddingClient) -> None:
        """Test client initialization."""
        assert client.provider == "openai"
        assert client.model == "text-embedding-3-small"
        assert client.dimension == 1536

    def test_metrics_initialized(self, client: EmbeddingClient) -> None:
        """Test that metrics are initialized."""
        assert client.metrics.total_tokens == 0
        assert client.metrics.total_requests == 0
        assert client.metrics.failed_requests == 0


class TestEmbed:
    """Tests for single text embedding."""

    @pytest.fixture
    def client(self) -> EmbeddingClient:
        """Create embedding client instance."""
        return EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

    @pytest.mark.asyncio
    async def test_embed_empty_text_raises(self, client: EmbeddingClient) -> None:
        """Test that embedding empty text raises error."""
        with pytest.raises(ValueError, match="empty text"):
            await client.embed("")

    @pytest.mark.asyncio
    async def test_embed_whitespace_raises(self, client: EmbeddingClient) -> None:
        """Test that embedding whitespace-only text raises error."""
        with pytest.raises(ValueError, match="empty text"):
            await client.embed("   \n\t   ")

    @pytest.mark.asyncio
    async def test_embed_calls_batch(self, client: EmbeddingClient) -> None:
        """Test that embed calls embed_batch."""
        mock_embedding = [0.1] * 1536

        with patch.object(
            client, "embed_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = [mock_embedding]

            result = await client.embed("Test text")

            mock_batch.assert_called_once_with(["Test text"], batch_size=1)
            assert result == mock_embedding


class TestEmbedBatch:
    """Tests for batch embedding."""

    @pytest.fixture
    def client(self) -> EmbeddingClient:
        """Create embedding client instance."""
        return EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self, client: EmbeddingClient) -> None:
        """Test embedding empty list returns empty list."""
        result = await client.embed_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_filters_empty(self, client: EmbeddingClient) -> None:
        """Test that empty texts in batch get zero vectors."""
        with patch.object(
            client, "_embed_with_retry", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [[0.1] * 1536]

            result = await client.embed_batch(["", "Valid text", "   "])

            # Should call embed for valid text only
            mock_embed.assert_called_once()

            # Result should have 3 items
            assert len(result) == 3
            # First and third should be zero vectors
            assert result[0] == [0.0] * 1536
            assert result[2] == [0.0] * 1536
            # Second should be the embedding
            assert result[1] == [0.1] * 1536

    @pytest.mark.asyncio
    async def test_embed_batch_tracks_requests(self, client: EmbeddingClient) -> None:
        """Test that batch embedding tracks request metrics."""
        with patch.object(
            client, "_embed_with_retry", new_callable=AsyncMock
        ) as mock_embed:
            mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

            await client.embed_batch(["Text 1", "Text 2"])

            assert client.metrics.total_requests >= 1


class TestEmbedWithRetry:
    """Tests for retry logic."""

    @pytest.fixture
    def client(self) -> EmbeddingClient:
        """Create embedding client instance."""
        return EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, client: EmbeddingClient) -> None:
        """Test that embedding retries on failure."""
        call_count = 0

        async def mock_embed(texts: list[str]) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return [[0.1] * 1536 for _ in texts]

        with patch.object(client, "_embed_openai", side_effect=mock_embed):
            result = await client._embed_with_retry(
                ["Test"], max_retries=3, base_delay=0.01
            )

            assert call_count == 2
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, client: EmbeddingClient) -> None:
        """Test that error is raised after max retries."""
        with patch.object(
            client,
            "_embed_openai",
            new_callable=AsyncMock,
            side_effect=Exception("Persistent failure"),
        ):
            with pytest.raises(Exception, match="Persistent failure"):
                await client._embed_with_retry(
                    ["Test"], max_retries=2, base_delay=0.01
                )

            assert client.metrics.failed_requests >= 2


class TestProviderIntegration:
    """Tests for provider-specific embedding."""

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self) -> None:
        """Test that unknown provider raises error."""
        client = EmbeddingClient(
            provider="unknown",
            model="some-model",
            dimension=1536,
        )

        with pytest.raises(ValueError, match="Unknown provider"):
            await client._embed_with_retry(["Test"], max_retries=1)

    @pytest.mark.asyncio
    async def test_openai_embedding(self) -> None:
        """Test OpenAI embedding with mocked client."""
        client = EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage = MagicMock(total_tokens=10)

        mock_openai = AsyncMock()
        mock_openai.embeddings.create = AsyncMock(return_value=mock_response)
        client._openai_client = mock_openai

        result = await client._embed_openai(["Test text"])

        assert len(result) == 1
        assert result[0] == [0.1] * 1536

    @pytest.mark.asyncio
    async def test_azure_embedding(self) -> None:
        """Test Azure OpenAI embedding with mocked client."""
        client = EmbeddingClient(
            provider="azure",
            model="text-embedding-ada-002",
            dimension=1536,
        )

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.2] * 1536)]
        mock_response.usage = MagicMock(total_tokens=15)

        mock_azure = AsyncMock()
        mock_azure.embeddings.create = AsyncMock(return_value=mock_response)
        client._azure_client = mock_azure

        result = await client._embed_azure(["Test text"])

        assert len(result) == 1
        assert result[0] == [0.2] * 1536


class TestEmbeddingMetrics:
    """Tests for EmbeddingMetrics model."""

    def test_metrics_defaults(self) -> None:
        """Test metrics default values."""
        metrics = EmbeddingMetrics()

        assert metrics.total_tokens == 0
        assert metrics.total_requests == 0
        assert metrics.total_latency_ms == 0
        assert metrics.failed_requests == 0

    def test_metrics_update(self) -> None:
        """Test updating metrics."""
        metrics = EmbeddingMetrics()
        metrics.total_tokens += 100
        metrics.total_requests += 1
        metrics.total_latency_ms += 50.5

        assert metrics.total_tokens == 100
        assert metrics.total_requests == 1
        assert metrics.total_latency_ms == 50.5


class TestClose:
    """Tests for client cleanup."""

    @pytest.mark.asyncio
    async def test_close_no_clients(self) -> None:
        """Test closing when no clients are initialized."""
        client = EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

        # Should not raise
        await client.close()

    @pytest.mark.asyncio
    async def test_close_with_openai_client(self) -> None:
        """Test closing with initialized OpenAI client."""
        client = EmbeddingClient(
            provider="openai",
            model="text-embedding-3-small",
            dimension=1536,
        )

        mock_openai = AsyncMock()
        client._openai_client = mock_openai

        await client.close()

        mock_openai.close.assert_called_once()
        assert client._openai_client is None
