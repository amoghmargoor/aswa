"""Tests for retrieval pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from aswa_query.retrieval.pipeline import RetrievalPipeline
from aswa_query.retrieval.models import (
    SearchResult, InsightResult, RetrievalResult, ContentType
)
from aswa_query.parser.models import ParsedQuery, QueryIntent
from aswa_query.config import Settings


@pytest.fixture
def settings():
    return Settings(
        qdrant_url="http://localhost:6333",
        qdrant_collection="test_chunks",
        insight_engine_url="http://localhost:8002",
        llm_max_tokens=4000,
        min_relevance_score=0.5,
    )


@pytest.fixture
def mock_vector_searcher():
    searcher = MagicMock()
    searcher.search = AsyncMock(return_value=[
        SearchResult(
            id="chunk-1",
            content="Test chunk content",
            content_type=ContentType.DOCUMENT_CHUNK,
            score=0.85,
            document_id=uuid4(),
            document_name="test.pdf",
            chunk_index=0,
        ),
    ])
    return searcher


@pytest.fixture
def mock_insight_retriever():
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=[
        InsightResult(
            id=uuid4(),
            title="Test Insight",
            description="Test insight description",
            insight_type="risk",
            confidence=0.8,
            score=0.75,
        ),
    ])
    return retriever


@pytest.fixture
def sample_query():
    return ParsedQuery(
        original_query="What are the revenue risks?",
        normalized_query="revenue risks",
        intent=QueryIntent.RISK,
        keywords=["revenue", "risks"],
    )


@pytest.fixture
def pipeline(settings, mock_vector_searcher, mock_insight_retriever):
    return RetrievalPipeline(
        settings=settings,
        vector_searcher=mock_vector_searcher,
        insight_retriever=mock_insight_retriever,
    )


class TestRetrievalPipeline:
    """Test RetrievalPipeline class."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_chunks_and_insights(
        self, pipeline, sample_query, mock_vector_searcher, mock_insight_retriever
    ):
        """Test that retrieve returns both chunks and insights."""
        tenant_id = uuid4()

        result = await pipeline.retrieve(sample_query, tenant_id)

        assert isinstance(result, RetrievalResult)
        assert len(result.document_chunks) > 0
        assert len(result.insights) > 0
        assert result.retrieval_time_ms >= 0

    @pytest.mark.asyncio
    async def test_retrieve_without_chunks(
        self, pipeline, sample_query, mock_vector_searcher
    ):
        """Test retrieve with include_chunks=False."""
        tenant_id = uuid4()

        result = await pipeline.retrieve(
            sample_query, tenant_id, include_chunks=False
        )

        mock_vector_searcher.search.assert_not_called()
        assert result.document_chunks == []

    @pytest.mark.asyncio
    async def test_retrieve_without_insights(
        self, pipeline, sample_query, mock_insight_retriever
    ):
        """Test retrieve with include_insights=False."""
        tenant_id = uuid4()

        result = await pipeline.retrieve(
            sample_query, tenant_id, include_insights=False
        )

        mock_insight_retriever.retrieve.assert_not_called()
        assert result.insights == []

    @pytest.mark.asyncio
    async def test_retrieve_handles_chunk_error(
        self, settings, mock_insight_retriever, sample_query
    ):
        """Test that retrieve handles chunk retrieval errors gracefully."""
        mock_searcher = MagicMock()
        mock_searcher.search = AsyncMock(side_effect=Exception("Search failed"))

        pipeline = RetrievalPipeline(
            settings=settings,
            vector_searcher=mock_searcher,
            insight_retriever=mock_insight_retriever,
        )

        tenant_id = uuid4()
        result = await pipeline.retrieve(sample_query, tenant_id)

        # Should still return insights even if chunks fail
        assert result.document_chunks == []
        assert len(result.insights) > 0

    @pytest.mark.asyncio
    async def test_retrieve_handles_insight_error(
        self, settings, mock_vector_searcher, sample_query
    ):
        """Test that retrieve handles insight retrieval errors gracefully."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(side_effect=Exception("Insight failed"))

        pipeline = RetrievalPipeline(
            settings=settings,
            vector_searcher=mock_vector_searcher,
            insight_retriever=mock_retriever,
        )

        tenant_id = uuid4()
        result = await pipeline.retrieve(sample_query, tenant_id)

        # Should still return chunks even if insights fail
        assert len(result.document_chunks) > 0
        assert result.insights == []

    @pytest.mark.asyncio
    async def test_retrieve_and_build_context(self, pipeline, sample_query):
        """Test retrieve_and_build_context returns both results."""
        tenant_id = uuid4()

        result, context = await pipeline.retrieve_and_build_context(
            sample_query, tenant_id
        )

        assert isinstance(result, RetrievalResult)
        assert context is not None
        assert context.token_count >= 0

    @pytest.mark.asyncio
    async def test_retrieve_respects_limits(
        self, pipeline, sample_query, mock_vector_searcher
    ):
        """Test that retrieve passes limits to searchers."""
        tenant_id = uuid4()

        await pipeline.retrieve(
            sample_query, tenant_id,
            max_chunks=5,
            max_insights=3,
        )

        call_args = mock_vector_searcher.search.call_args
        assert call_args.kwargs.get('limit') == 5

    @pytest.mark.asyncio
    async def test_retrieve_for_document(
        self, pipeline, mock_vector_searcher
    ):
        """Test retrieving all content for a specific document."""
        document_id = uuid4()
        tenant_id = uuid4()

        mock_vector_searcher.get_document_chunks = AsyncMock(return_value=[
            SearchResult(
                id="chunk-1",
                content="Document chunk",
                content_type=ContentType.DOCUMENT_CHUNK,
                score=1.0,
            ),
        ])

        result = await pipeline.retrieve_for_document(document_id, tenant_id)

        assert len(result.document_chunks) == 1
        assert "document:" in result.query


class TestRetrievalResult:
    """Test RetrievalResult model."""

    def test_retrieval_result_defaults(self):
        """Test RetrievalResult default values."""
        result = RetrievalResult(
            query="test query",
            document_chunks=[],
            insights=[],
            total_chunks=0,
        )

        assert result.query == "test query"
        assert result.total_insights == 0
        assert result.retrieval_time_ms == 0

    def test_retrieval_result_with_content(self):
        """Test RetrievalResult with chunks and insights."""
        chunk = SearchResult(
            id="chunk-1",
            content="Test",
            content_type=ContentType.DOCUMENT_CHUNK,
            score=0.9,
        )
        insight = InsightResult(
            id=uuid4(),
            title="Test",
            description="Test",
            insight_type="risk",
            confidence=0.8,
            score=0.8,
        )

        result = RetrievalResult(
            query="test",
            document_chunks=[chunk],
            insights=[insight],
            total_chunks=1,
            total_insights=1,
            retrieval_time_ms=100,
        )

        assert result.total_chunks == 1
        assert result.total_insights == 1
        assert result.retrieval_time_ms == 100
