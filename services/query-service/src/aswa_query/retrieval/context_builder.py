from typing import Any
import tiktoken
import structlog

from .models import SearchResult, InsightResult, ContextWindow, RetrievalResult

logger = structlog.get_logger()


class ContextBuilder:
    """Build context windows for LLM generation."""

    def __init__(
        self,
        max_tokens: int = 4000,
        model: str = "gpt-4",
    ):
        self.max_tokens = max_tokens
        self.model = model
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def build_context(
        self,
        retrieval_result: RetrievalResult,
        include_insights: bool = True,
        include_chunks: bool = True,
    ) -> ContextWindow:
        """Build context window from retrieval results.

        Args:
            retrieval_result: Results from retrieval pipeline
            include_insights: Include insights in context
            include_chunks: Include document chunks in context

        Returns:
            ContextWindow with formatted content
        """
        sections = []
        sources = []
        total_tokens = 0

        # Add document chunks
        if include_chunks and retrieval_result.document_chunks:
            chunk_section, chunk_sources, chunk_tokens = self._format_chunks(
                retrieval_result.document_chunks,
                self.max_tokens - total_tokens,
            )
            if chunk_section:
                sections.append(chunk_section)
                sources.extend(chunk_sources)
                total_tokens += chunk_tokens

        # Add insights
        if include_insights and retrieval_result.insights:
            insight_section, insight_sources, insight_tokens = self._format_insights(
                retrieval_result.insights,
                self.max_tokens - total_tokens,
            )
            if insight_section:
                sections.append(insight_section)
                sources.extend(insight_sources)
                total_tokens += insight_tokens

        content = "\n\n".join(sections)

        return ContextWindow(
            content=content,
            token_count=total_tokens,
            sources=sources,
            metadata={
                "chunk_count": len(retrieval_result.document_chunks),
                "insight_count": len(retrieval_result.insights),
            },
        )

    def _format_chunks(
        self,
        chunks: list[SearchResult],
        max_tokens: int,
    ) -> tuple[str, list[str], int]:
        """Format document chunks for context."""
        if not chunks:
            return "", [], 0

        lines = ["## Relevant Document Excerpts\n"]
        sources = []
        tokens_used = self._count_tokens(lines[0])

        for i, chunk in enumerate(chunks, 1):
            # Format chunk
            source_ref = chunk.source_reference
            chunk_text = f"### [{i}] {source_ref}\n{chunk.content}\n"

            chunk_tokens = self._count_tokens(chunk_text)
            if tokens_used + chunk_tokens > max_tokens:
                break

            lines.append(chunk_text)
            sources.append(source_ref)
            tokens_used += chunk_tokens

        return "\n".join(lines), sources, tokens_used

    def _format_insights(
        self,
        insights: list[InsightResult],
        max_tokens: int,
    ) -> tuple[str, list[str], int]:
        """Format insights for context."""
        if not insights:
            return "", [], 0

        lines = ["## Extracted Insights\n"]
        sources = []
        tokens_used = self._count_tokens(lines[0])

        for insight in insights:
            # Format insight
            insight_text = f"### {insight.insight_type.upper()}: {insight.title}\n"
            insight_text += f"{insight.description}\n"

            if insight.severity:
                insight_text += f"Severity: {insight.severity}\n"
            if insight.category:
                insight_text += f"Category: {insight.category}\n"

            insight_text += f"Confidence: {insight.confidence:.0%}\n"

            insight_tokens = self._count_tokens(insight_text)
            if tokens_used + insight_tokens > max_tokens:
                break

            lines.append(insight_text)
            if insight.document_name:
                sources.append(insight.document_name)
            tokens_used += insight_tokens

        return "\n".join(lines), sources, tokens_used

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def build_summary_context(
        self,
        retrieval_result: RetrievalResult,
    ) -> ContextWindow:
        """Build condensed context for summary generation."""
        # For summaries, prioritize insights over raw chunks
        sections = []
        sources = []
        total_tokens = 0

        # Add insight summary
        if retrieval_result.insights:
            insight_types = {}
            for insight in retrieval_result.insights:
                itype = insight.insight_type
                if itype not in insight_types:
                    insight_types[itype] = []
                insight_types[itype].append(insight)

            summary_lines = ["## Key Insights Summary\n"]
            for itype, insights in insight_types.items():
                summary_lines.append(f"### {itype.title()} ({len(insights)})")
                for insight in insights[:3]:  # Top 3 per type
                    summary_lines.append(f"- {insight.title}")
                    if insight.document_name:
                        sources.append(insight.document_name)

            section = "\n".join(summary_lines)
            sections.append(section)
            total_tokens += self._count_tokens(section)

        # Add abbreviated chunks
        if retrieval_result.document_chunks and total_tokens < self.max_tokens - 500:
            chunk_lines = ["## Key Document Points\n"]
            for chunk in retrieval_result.document_chunks[:5]:
                # Take first 200 chars of each chunk
                abbreviated = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
                chunk_lines.append(f"- {abbreviated}")
                if chunk.source_reference:
                    sources.append(chunk.source_reference)

            section = "\n".join(chunk_lines)
            sections.append(section)
            total_tokens += self._count_tokens(section)

        return ContextWindow(
            content="\n\n".join(sections),
            token_count=total_tokens,
            sources=list(set(sources)),
        )
