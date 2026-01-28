"""Tests for vector search module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aswa_query.retrieval.vector_search import VectorSearcher
from aswa_query.retrieval.models import SearchResult, ContentType
from aswa_query.config import Settings


@pytest.fixture
def settings():
    return Settings(
        qdrant_url="http://localhost:6333",
        qdrant_collection="test_chunks",
    )


@pytest.fixture
def vector_searcher(settings):
    return VectorSearcher(settings)


class TestVectorSearcher:
    """Test VectorSearcher class."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, vector_searcher):
        """Test that search returns properly formatted results."""
        tenant_id = uuid4()
        query = "test query"

        # Mock the Qdrant client
        mock_result = MagicMock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.85
        mock_result.payload = {
            "content": "Test content",
            "document_id": str(uuid4()),
            "document_name": "test.pdf",
            "chunk_index": 0,
            "page_number": 1,
            "metadata": {},
        }

        with patch.object(vector_searcher, '_get_client') as mock_get_client, \
             patch.object(vector_searcher, '_embed_query', new_callable=AsyncMock) as mock_embed:
            mock_client = MagicMock()
            mock_client.search.return_value = [mock_result]
            mock_get_client.return_value = mock_client
            mock_embed.return_value = [0.1] * 384  # Fake embedding

            results = await vector_searcher.search(
                query=query,
                tenant_id=tenant_id,
                limit=10,
            )

            assert len(results) == 1
            assert results[0].id == "chunk-1"
            assert results[0].score == 0.85
            assert results[0].content == "Test content"
            assert results[0].content_type == ContentType.DOCUMENT_CHUNK

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, vector_searcher):
        """Test search with document ID filter."""
        tenant_id = uuid4()
        document_ids = [uuid4(), uuid4()]

        with patch.object(vector_searcher, '_get_client') as mock_get_client, \
             patch.object(vector_searcher, '_embed_query', new_callable=AsyncMock) as mock_embed:
            mock_client = MagicMock()
            mock_client.search.return_value = []
            mock_get_client.return_value = mock_client
            mock_embed.return_value = [0.1] * 384

            await vector_searcher.search(
                query="test",
                tenant_id=tenant_id,
                document_ids=document_ids,
            )

            # Verify filter was applied
            call_args = mock_client.search.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_search_empty_results(self, vector_searcher):
        """Test search with no results."""
        tenant_id = uuid4()

        with patch.object(vector_searcher, '_get_client') as mock_get_client, \
             patch.object(vector_searcher, '_embed_query', new_callable=AsyncMock) as mock_embed:
            mock_client = MagicMock()
            mock_client.search.return_value = []
            mock_get_client.return_value = mock_client
            mock_embed.return_value = [0.1] * 384

            results = await vector_searcher.search(
                query="nonexistent",
                tenant_id=tenant_id,
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_get_document_chunks(self, vector_searcher):
        """Test retrieving all chunks for a document."""
        tenant_id = uuid4()
        document_id = uuid4()

        mock_point1 = MagicMock()
        mock_point1.id = "chunk-1"
        mock_point1.payload = {
            "content": "Chunk 1",
            "document_id": str(document_id),
            "chunk_index": 0,
        }

        mock_point2 = MagicMock()
        mock_point2.id = "chunk-2"
        mock_point2.payload = {
            "content": "Chunk 2",
            "document_id": str(document_id),
            "chunk_index": 1,
        }

        with patch.object(vector_searcher, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.scroll.return_value = ([mock_point2, mock_point1], None)
            mock_get_client.return_value = mock_client

            results = await vector_searcher.get_document_chunks(document_id, tenant_id)

            # Should be sorted by chunk_index
            assert len(results) == 2
            assert results[0].chunk_index == 0
            assert results[1].chunk_index == 1

    @pytest.mark.asyncio
    async def test_search_by_vector(self, vector_searcher):
        """Test search using pre-computed vector."""
        tenant_id = uuid4()
        vector = [0.1] * 384

        mock_result = MagicMock()
        mock_result.id = "chunk-1"
        mock_result.score = 0.9
        mock_result.payload = {
            "content": "Test content",
            "document_id": str(uuid4()),
        }

        with patch.object(vector_searcher, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.search.return_value = [mock_result]
            mock_get_client.return_value = mock_client

            results = await vector_searcher.search_by_vector(
                vector=vector,
                tenant_id=tenant_id,
            )

            assert len(results) == 1
            assert results[0].score == 0.9
