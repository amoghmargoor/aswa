import pytest
from uuid import uuid4

from aswa_query.generation.validator import AnswerValidator
from aswa_query.generation.models import GeneratedAnswer
from aswa_query.retrieval.models import ContextWindow


class TestAnswerValidator:
    @pytest.fixture
    def validator(self):
        return AnswerValidator()

    def test_validate_basic_empty_answer(self, validator):
        """Test validation of empty answer."""
        answer = GeneratedAnswer(answer="", query="test")
        context = ContextWindow(content="Some context", token_count=10, sources=[])

        result = validator.validate_basic(answer, context)

        assert not result.is_valid
        assert "too short" in result.issues[0].lower()

    def test_validate_basic_no_citations(self, validator):
        """Test validation when citations missing."""
        answer = GeneratedAnswer(
            answer="This is a detailed answer without any citations.",
            query="test",
        )
        context = ContextWindow(
            content="Source content",
            token_count=50,
            sources=["Doc1.pdf", "Doc2.pdf"],
        )

        result = validator.validate_basic(answer, context)

        assert "citations" in str(result.issues).lower()

    def test_validate_citations_valid(self, validator):
        """Test validation with valid citations."""
        answer = GeneratedAnswer(
            answer="This is correct [1]. This is also correct [2].",
            query="test",
        )

        result = validator.validate_citations(answer, max_citation_index=3)

        assert result.is_valid

    def test_validate_citations_invalid_index(self, validator):
        """Test validation with invalid citation index."""
        answer = GeneratedAnswer(
            answer="This references [10] which doesn't exist.",
            query="test",
        )

        result = validator.validate_citations(answer, max_citation_index=3)

        assert not result.is_valid
        assert any("invalid" in issue.lower() for issue in result.issues)
