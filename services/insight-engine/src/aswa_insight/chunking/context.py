from dataclasses import dataclass, field
from typing import Any

import structlog

from .splitter import Chunk

logger = structlog.get_logger()


@dataclass
class ChunkContext:
    """Context information for a chunk."""

    chunk: Chunk
    document_title: str | None = None
    document_summary: str | None = None
    previous_chunk_summary: str | None = None
    section_title: str | None = None
    position_description: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Convert to context string for prompts."""
        parts = []

        if self.document_title:
            parts.append(f"Document: {self.document_title}")

        if self.document_summary:
            parts.append(f"Document Summary: {self.document_summary}")

        if self.section_title:
            parts.append(f"Section: {self.section_title}")

        if self.position_description:
            parts.append(f"Position: {self.position_description}")

        if self.previous_chunk_summary:
            parts.append(f"Previous Content: {self.previous_chunk_summary}")

        return "\n".join(parts)


class ChunkContextBuilder:
    """Build context for chunks to preserve document understanding."""

    def __init__(
        self,
        include_document_summary: bool = True,
        include_position: bool = True,
        include_previous_summary: bool = True,
        max_summary_length: int = 500,
    ):
        self.include_document_summary = include_document_summary
        self.include_position = include_position
        self.include_previous_summary = include_previous_summary
        self.max_summary_length = max_summary_length

    def build_contexts(
        self,
        chunks: list[Chunk],
        document_title: str | None = None,
        document_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[ChunkContext]:
        """Build context for all chunks.

        Args:
            chunks: List of chunks
            document_title: Optional document title
            document_summary: Optional document summary
            metadata: Optional document metadata

        Returns:
            List of chunk contexts
        """
        contexts = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            # Position description
            position = None
            if self.include_position:
                if total_chunks == 1:
                    position = "Entire document"
                elif i == 0:
                    position = f"Beginning of document (chunk 1 of {total_chunks})"
                elif i == total_chunks - 1:
                    position = f"End of document (chunk {i + 1} of {total_chunks})"
                else:
                    position = f"Middle of document (chunk {i + 1} of {total_chunks})"

            # Previous chunk summary
            prev_summary = None
            if self.include_previous_summary and i > 0:
                prev_summary = self._create_chunk_summary(chunks[i - 1])

            # Detect section title if present
            section_title = self._detect_section_title(chunk.text)

            context = ChunkContext(
                chunk=chunk,
                document_title=document_title,
                document_summary=document_summary if self.include_document_summary else None,
                previous_chunk_summary=prev_summary,
                section_title=section_title,
                position_description=position,
                metadata=metadata or {},
            )
            contexts.append(context)

        return contexts

    def _create_chunk_summary(self, chunk: Chunk) -> str:
        """Create a brief summary of a chunk for context."""
        text = chunk.text[: self.max_summary_length]

        # Truncate at sentence boundary
        last_period = text.rfind(".")
        if last_period > self.max_summary_length // 2:
            text = text[: last_period + 1]

        return text.strip() + "..."

    def _detect_section_title(self, text: str) -> str | None:
        """Detect section title from chunk start."""
        lines = text.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0].strip()

        # Check for markdown headers
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()

        # Check for numbered headers
        if len(first_line) < 100 and first_line[0].isdigit():
            return first_line

        # Check for ALL CAPS headers
        if first_line.isupper() and len(first_line) < 100:
            return first_line

        return None
