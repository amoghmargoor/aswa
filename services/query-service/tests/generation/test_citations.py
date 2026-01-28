import pytest
from uuid import uuid4

from aswa_query.generation.citations import CitationExtractor
from aswa_query.generation.models import Citation
from aswa_query.retrieval.models import SearchResult, InsightResult, ContentType


class TestCitationExtractor:
    @pytest.fixture
    def extractor(self):
        return CitationExtractor()

    def test_build_citation_map(self, extractor):
        """Test building citation map."""
        chunks = [
            SearchResult(id="1", content="Content 1", content_type=ContentType.DOCUMENT_CHUNK, score=0.9, document_id=uuid4(), document_name="Doc1.pdf"),
            SearchResult(id="2", content="Content 2", content_type=ContentType.DOCUMENT_CHUNK, score=0.8, document_id=uuid4(), document_name="Doc2.pdf"),
        ]
        insights = [
            InsightResult(id=uuid4(), title="Insight", description="Description", insight_type="risk", confidence=0.8, score=0.85),
        ]

        citation_map = extractor.build_citation_map(chunks, insights)

        assert len(citation_map) == 3
        assert 1 in citation_map
        assert 2 in citation_map
        assert 3 in citation_map

    def test_extract_used_citations(self, extractor):
        """Test extracting used citations."""
        citation_map = {
            1: Citation(index=1, document_id=uuid4(), document_name="Doc1"),
            2: Citation(index=2, document_id=uuid4(), document_name="Doc2"),
            3: Citation(index=3, document_id=uuid4(), document_name="Doc3"),
        }

        answer = "This is from the first source [1]. This is from the third [3]."

        used = extractor.extract_used_citations(answer, citation_map)

        assert len(used) == 2
        assert used[0].index == 1
        assert used[1].index == 3

    def test_renumber_citations(self, extractor):
        """Test citation renumbering."""
        citations = [
            Citation(index=3, document_id=uuid4(), document_name="Doc3"),
            Citation(index=7, document_id=uuid4(), document_name="Doc7"),
        ]

        answer = "Source [3] says this. Source [7] says that."

        updated_answer, renumbered = extractor.renumber_citations(answer, citations)

        assert "[1]" in updated_answer
        assert "[2]" in updated_answer
        assert "[3]" not in updated_answer
        assert renumbered[0].index == 1
        assert renumbered[1].index == 2


class TestCitation:
    def test_format_with_page(self):
        """Test citation formatting with page number."""
        citation = Citation(
            index=1,
            document_id=uuid4(),
            document_name="Report.pdf",
            page_number=42,
        )

        formatted = citation.format()
        assert "[1]" in formatted
        assert "Report.pdf" in formatted
        assert "p.42" in formatted

    def test_format_without_page(self):
        """Test citation formatting without page."""
        citation = Citation(
            index=2,
            document_id=uuid4(),
            document_name="Doc.pdf",
        )

        formatted = citation.format()
        assert "[2]" in formatted
        assert "Doc.pdf" in formatted
