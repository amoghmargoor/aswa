import re
from typing import Any
from uuid import UUID
import structlog

from aswa_query.retrieval.models import SearchResult, InsightResult
from .models import Citation

logger = structlog.get_logger()


class CitationExtractor:
    """Extract and manage citations in generated answers."""

    def __init__(self):
        self._citation_pattern = re.compile(r'\[(\d+)\]')

    def build_citation_map(
        self,
        chunks: list[SearchResult],
        insights: list[InsightResult],
    ) -> dict[int, Citation]:
        """Build a map of citation indices to sources.

        Args:
            chunks: Document chunks
            insights: Insights

        Returns:
            Dict mapping index to Citation
        """
        citation_map = {}
        index = 1

        # Add chunk citations
        for chunk in chunks:
            citation_map[index] = Citation(
                index=index,
                document_id=chunk.document_id,
                document_name=chunk.document_name or f"Document {chunk.document_id}",
                page_number=chunk.page_number,
                excerpt=chunk.content[:200] if chunk.content else "",
                relevance_score=chunk.score,
            )
            index += 1

        # Add insight citations
        for insight in insights:
            citation_map[index] = Citation(
                index=index,
                document_id=insight.document_id,
                document_name=insight.document_name or f"Insight: {insight.title[:50]}",
                excerpt=insight.description[:200] if insight.description else "",
                relevance_score=insight.score,
            )
            index += 1

        return citation_map

    def extract_used_citations(
        self,
        answer: str,
        citation_map: dict[int, Citation],
    ) -> list[Citation]:
        """Extract citations actually used in the answer.

        Args:
            answer: Generated answer text
            citation_map: Available citations

        Returns:
            List of citations used in answer
        """
        matches = self._citation_pattern.findall(answer)
        used_indices = set(int(m) for m in matches)

        used_citations = []
        for index in sorted(used_indices):
            if index in citation_map:
                used_citations.append(citation_map[index])

        return used_citations

    def renumber_citations(
        self,
        answer: str,
        used_citations: list[Citation],
    ) -> tuple[str, list[Citation]]:
        """Renumber citations sequentially starting from 1.

        Args:
            answer: Answer with citations
            used_citations: Citations used in answer

        Returns:
            Tuple of (updated_answer, renumbered_citations)
        """
        if not used_citations:
            return answer, []

        # Build old->new index mapping
        old_to_new = {}
        renumbered = []

        for new_index, citation in enumerate(used_citations, 1):
            old_to_new[citation.index] = new_index
            new_citation = Citation(
                index=new_index,
                document_id=citation.document_id,
                document_name=citation.document_name,
                page_number=citation.page_number,
                excerpt=citation.excerpt,
                relevance_score=citation.relevance_score,
            )
            renumbered.append(new_citation)

        # Replace old indices with new
        def replace_citation(match):
            old_index = int(match.group(1))
            new_index = old_to_new.get(old_index, old_index)
            return f"[{new_index}]"

        updated_answer = self._citation_pattern.sub(replace_citation, answer)

        return updated_answer, renumbered

    def add_missing_citations(
        self,
        answer: str,
        citation_map: dict[int, Citation],
        threshold: float = 0.8,
    ) -> str:
        """Add citations where text matches source but isn't cited.

        Args:
            answer: Answer text
            citation_map: Available citations
            threshold: Text match threshold

        Returns:
            Answer with added citations
        """
        # Simple implementation: find sentences that match sources
        sentences = answer.split('. ')
        updated_sentences = []

        for sentence in sentences:
            # Check if sentence already has citation
            if self._citation_pattern.search(sentence):
                updated_sentences.append(sentence)
                continue

            # Try to find matching source
            best_match_index = None
            best_match_score = 0

            for index, citation in citation_map.items():
                if not citation.excerpt:
                    continue

                # Simple word overlap check
                sentence_words = set(sentence.lower().split())
                source_words = set(citation.excerpt.lower().split())

                if not sentence_words:
                    continue

                overlap = len(sentence_words & source_words) / len(sentence_words)
                if overlap > best_match_score and overlap >= threshold:
                    best_match_score = overlap
                    best_match_index = index

            if best_match_index:
                sentence = f"{sentence} [{best_match_index}]"

            updated_sentences.append(sentence)

        return '. '.join(updated_sentences)

    def format_citations_section(
        self,
        citations: list[Citation],
    ) -> str:
        """Format citations as a reference section.

        Args:
            citations: List of citations

        Returns:
            Formatted citation section
        """
        if not citations:
            return ""

        lines = ["\n\n---\n**Sources:**"]
        for citation in citations:
            line = f"\n[{citation.index}] {citation.document_name}"
            if citation.page_number:
                line += f", page {citation.page_number}"
            lines.append(line)

        return "".join(lines)
