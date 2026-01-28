import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_query.generation.generator import AnswerGenerator
from aswa_query.generation.models import GeneratedAnswer
from aswa_query.retrieval.models import RetrievalResult, SearchResult, ContextWindow, ContentType
from aswa_query.parser.models import ParsedQuery, QueryIntent
from aswa_query.config import Settings


class TestAnswerGenerator:
    @pytest.fixture
    def settings(self):
        return Settings()

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.complete = AsyncMock(return_value="This is the answer based on the context [1]. More info [2].")
        return llm

    @pytest.fixture
    def generator(self, settings, mock_llm):
        return AnswerGenerator(settings, mock_llm)

    @pytest.mark.asyncio
    async def test_generate_answer(self, generator, mock_llm):
        """Test basic answer generation."""
        query = ParsedQuery(
            original_query="What are the risks?",
            normalized_query="what are the risks",
            intent=QueryIntent.RISK,
            confidence=0.9,
        )

        retrieval_result = RetrievalResult(
            query="test",
            document_chunks=[
                SearchResult(id="1", content="Risk content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc1.pdf"),
            ],
        )

        context = ContextWindow(
            content="Test context",
            token_count=100,
            sources=["Doc1.pdf"],
        )

        answer = await generator.generate(query, retrieval_result, context)

        assert isinstance(answer, GeneratedAnswer)
        assert len(answer.answer) > 0
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_includes_citations(self, generator):
        """Test that generated answer includes citations."""
        query = ParsedQuery(
            original_query="Test query",
            normalized_query="test query",
            intent=QueryIntent.FACTUAL,
            confidence=0.8,
        )

        retrieval_result = RetrievalResult(
            query="test",
            document_chunks=[
                SearchResult(id="1", content="Content", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc.pdf"),
            ],
        )

        context = ContextWindow(content="Context", token_count=50, sources=["Doc.pdf"])

        answer = await generator.generate(query, retrieval_result, context)

        assert answer.has_citations or "[" in answer.answer
