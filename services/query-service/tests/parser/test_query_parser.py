import pytest
from uuid import uuid4
from aswa_query.parser.query_parser import QueryParser
from aswa_query.parser.models import QueryIntent


class TestQueryParser:
    @pytest.fixture
    def parser(self):
        return QueryParser()

    def test_parse_simple_query(self, parser):
        """Test parsing a simple query."""
        result = parser.parse("What are the main risks?")
        assert result.original_query == "What are the main risks?"
        assert result.intent == QueryIntent.RISK
        assert len(result.keywords) > 0

    def test_parse_with_entities(self, parser):
        """Test parsing query with entities."""
        result = parser.parse("What is Acme Corp's revenue of $50 million?")
        assert len(result.entities) >= 1

    def test_parse_with_time(self, parser):
        """Test parsing query with temporal expression."""
        result = parser.parse("Show risks from last 30 days")
        assert result.time_range is not None
        assert result.has_temporal_constraint

    def test_parse_with_filters(self, parser):
        """Test parsing query with filters."""
        result = parser.parse("Show high confidence risks")
        assert len(result.filters) >= 1

    def test_parse_with_document_scope(self, parser):
        """Test parsing with document scope."""
        doc_ids = [uuid4(), uuid4()]
        result = parser.parse("Summarize the content", document_scope=doc_ids)
        assert result.document_scope == doc_ids

    def test_normalized_query(self, parser):
        """Test query normalization."""
        result = parser.parse("  What   ARE the   RISKS?  ")
        assert result.normalized_query == "what are the risks"

    def test_keyword_extraction(self, parser):
        """Test keyword extraction."""
        result = parser.parse("What are the financial risks for the company?")
        assert "financial" in result.keywords
        assert "risks" in result.keywords
        assert "company" in result.keywords
        # Stop words should be excluded
        assert "the" not in result.keywords
        assert "are" not in result.keywords

    def test_query_hash(self, parser):
        """Test query hash generation."""
        result1 = parser.parse("What are the risks?")
        result2 = parser.parse("What are the risks?")
        result3 = parser.parse("What are the opportunities?")

        hash1 = parser.get_query_hash(result1)
        hash2 = parser.get_query_hash(result2)
        hash3 = parser.get_query_hash(result3)

        assert hash1 == hash2  # Same query
        assert hash1 != hash3  # Different query

    def test_to_search_query(self, parser):
        """Test conversion to search query."""
        result = parser.parse("Show risks from last 30 days")
        search_query = parser.to_search_query(result)

        assert "query_text" in search_query
        assert "keywords" in search_query
        assert "filters" in search_query
