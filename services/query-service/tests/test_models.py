import pytest
from uuid import uuid4

from aswa_query.models.query import (
    QueryRequest,
    QueryResponse,
    QueryType,
    Citation,
    SearchRequest,
)


class TestQueryRequest:
    def test_valid_request(self):
        """Test valid query request."""
        request = QueryRequest(query="What are the risks?")
        assert request.query_type == QueryType.QUESTION
        assert request.max_results == 10

    def test_query_stripping(self):
        """Test query is stripped."""
        request = QueryRequest(query="  test query  ")
        assert request.query == "test query"

    def test_query_type_override(self):
        """Test query type override."""
        request = QueryRequest(query="test", query_type=QueryType.SUMMARY)
        assert request.query_type == QueryType.SUMMARY


class TestQueryResponse:
    def test_response_creation(self):
        """Test response creation."""
        response = QueryResponse(
            query="test",
            answer="answer",
            confidence=0.9,
            processing_time_ms=100,
        )
        assert response.query_id is not None
        assert response.confidence == 0.9


class TestCitation:
    def test_citation_creation(self):
        """Test citation creation."""
        citation = Citation(
            document_id=uuid4(),
            document_name="test.pdf",
            relevance_score=0.85,
            excerpt="Test excerpt",
        )
        assert citation.relevance_score == 0.85
