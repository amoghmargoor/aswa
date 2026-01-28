"""Tests for reranker module."""

import pytest
from uuid import uuid4

from aswa_query.retrieval.reranker import Reranker, RerankerConfig
from aswa_query.retrieval.models import SearchResult, InsightResult, ContentType


@pytest.fixture
def reranker():
    return Reranker()


@pytest.fixture
def sample_chunks():
    """Create sample search results for testing."""
    return [
        SearchResult(
            id="chunk-1",
            content="This document discusses revenue growth and market expansion.",
            content_type=ContentType.DOCUMENT_CHUNK,
            score=0.8,
            document_id=uuid4(),
            document_name="annual_report.pdf",
            chunk_index=0,
        ),
        SearchResult(
            id="chunk-2",
            content="The company achieved significant revenue milestones this quarter.",
            content_type=ContentType.DOCUMENT_CHUNK,
            score=0.75,
            document_id=uuid4(),
            document_name="quarterly_update.pdf",
            chunk_index=0,
        ),
        SearchResult(
            id="chunk-3",
            content="Employee satisfaction improved with new initiatives.",
            content_type=ContentType.DOCUMENT_CHUNK,
            score=0.7,
            document_id=uuid4(),
            document_name="hr_report.pdf",
            chunk_index=0,
        ),
    ]


@pytest.fixture
def sample_insights():
    """Create sample insights for testing."""
    return [
        InsightResult(
            id=uuid4(),
            title="Revenue Growth Trend",
            description="Revenue has grown 15% year over year.",
            insight_type="trend",
            confidence=0.9,
            score=0.85,
            document_id=uuid4(),
            document_name="annual_report.pdf",
        ),
        InsightResult(
            id=uuid4(),
            title="Market Expansion Opportunity",
            description="New market opportunities identified in Asia.",
            insight_type="opportunity",
            confidence=0.8,
            score=0.75,
            document_id=uuid4(),
            document_name="strategy.pdf",
        ),
    ]


class TestReranker:
    """Test Reranker class."""

    def test_rerank_chunks_with_keywords(self, reranker, sample_chunks):
        """Test reranking chunks boosts keyword matches."""
        keywords = ["revenue", "growth"]

        reranked = reranker.rerank_chunks(sample_chunks, keywords, max_results=3)

        # First chunk should stay first (has both keywords)
        assert reranked[0].id == "chunk-1"
        # Score should be boosted
        assert reranked[0].score > 0.8

    def test_rerank_chunks_empty_list(self, reranker):
        """Test reranking empty list returns empty."""
        result = reranker.rerank_chunks([], ["test"], max_results=5)
        assert result == []

    def test_rerank_chunks_respects_limit(self, reranker, sample_chunks):
        """Test reranking respects max_results limit."""
        result = reranker.rerank_chunks(sample_chunks, [], max_results=2)
        assert len(result) == 2

    def test_rerank_insights(self, reranker, sample_insights):
        """Test reranking insights."""
        keywords = ["revenue"]

        reranked = reranker.rerank_insights(sample_insights, keywords, max_results=2)

        assert len(reranked) == 2
        # First insight mentions revenue, should be ranked higher
        assert reranked[0].title == "Revenue Growth Trend"

    def test_rerank_insights_confidence_weight(self, reranker, sample_insights):
        """Test that confidence affects ranking."""
        # Use empty keywords to isolate confidence effect
        reranked = reranker.rerank_insights(sample_insights, [], max_results=2)

        # Higher confidence insight should rank first
        assert reranked[0].confidence >= reranked[1].confidence

    def test_combine_results_balanced(self, reranker, sample_chunks, sample_insights):
        """Test combining chunks and insights."""
        chunks, insights = reranker.combine_results(
            sample_chunks, sample_insights, max_total=4
        )

        # Should have some of each
        assert len(chunks) > 0
        assert len(insights) > 0
        assert len(chunks) + len(insights) <= 4

    def test_combine_results_handles_empty(self, reranker, sample_chunks):
        """Test combining when one list is empty."""
        chunks, insights = reranker.combine_results(
            sample_chunks, [], max_total=5
        )

        assert len(chunks) > 0
        assert insights == []

    def test_deduplicate_removes_similar(self, reranker):
        """Test deduplication removes near-duplicates."""
        chunks = [
            SearchResult(
                id="chunk-1",
                content="The revenue growth was significant this quarter.",
                content_type=ContentType.DOCUMENT_CHUNK,
                score=0.9,
            ),
            SearchResult(
                id="chunk-2",
                content="The revenue growth was significant this quarter.",  # Exact duplicate
                content_type=ContentType.DOCUMENT_CHUNK,
                score=0.85,
            ),
            SearchResult(
                id="chunk-3",
                content="Different content about employee satisfaction.",
                content_type=ContentType.DOCUMENT_CHUNK,
                score=0.8,
            ),
        ]

        deduplicated = reranker.deduplicate_results(chunks)

        assert len(deduplicated) == 2
        assert deduplicated[0].id == "chunk-1"
        assert deduplicated[1].id == "chunk-3"

    def test_deduplicate_preserves_unique(self, reranker, sample_chunks):
        """Test deduplication preserves unique content."""
        deduplicated = reranker.deduplicate_results(sample_chunks)

        # All sample chunks are unique
        assert len(deduplicated) == len(sample_chunks)

    def test_deduplicate_empty_list(self, reranker):
        """Test deduplication of empty list."""
        result = reranker.deduplicate_results([])
        assert result == []

    def test_deduplicate_single_item(self, reranker, sample_chunks):
        """Test deduplication of single item."""
        result = reranker.deduplicate_results([sample_chunks[0]])
        assert len(result) == 1


class TestRerankerConfig:
    """Test RerankerConfig defaults."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RerankerConfig()

        assert config.chunk_weight == 0.6
        assert config.insight_weight == 0.4
        assert config.keyword_boost == 0.15

    def test_custom_config(self):
        """Test custom configuration."""
        config = RerankerConfig(
            chunk_weight=0.7,
            keyword_boost=0.2,
        )

        assert config.chunk_weight == 0.7
        assert config.keyword_boost == 0.2

    def test_reranker_uses_config(self):
        """Test reranker uses provided config."""
        config = RerankerConfig(keyword_boost=0.5)
        reranker = Reranker(config)

        assert reranker.config.keyword_boost == 0.5
