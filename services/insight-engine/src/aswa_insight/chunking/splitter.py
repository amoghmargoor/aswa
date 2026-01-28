from dataclasses import dataclass, field
from enum import Enum
import re

import structlog

logger = structlog.get_logger()


class ChunkingStrategy(str, Enum):
    """Strategies for chunking text."""

    FIXED_SIZE = "fixed_size"  # Fixed character count
    SENTENCE = "sentence"  # Split on sentence boundaries
    PARAGRAPH = "paragraph"  # Split on paragraph boundaries
    SECTION = "section"  # Split on section headers
    SEMANTIC = "semantic"  # Split on semantic boundaries
    RECURSIVE = "recursive"  # Recursively split large chunks


@dataclass
class Chunk:
    """A chunk of text from a document."""

    index: int
    text: str
    start_offset: int
    end_offset: int
    metadata: dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class TextSplitter:
    """Split text into chunks for processing."""

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """Initialize text splitter.

        Args:
            strategy: Chunking strategy to use
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            min_chunk_size: Minimum chunk size to keep
        """
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Regex patterns for splitting
        self._section_pattern = re.compile(r"\n(?=#{1,3}\s|\d+\.\s|[A-Z][A-Z\s]+:)")
        self._paragraph_pattern = re.compile(r"\n\s*\n")
        self._sentence_pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def split(self, text: str) -> list[Chunk]:
        """Split text into chunks.

        Args:
            text: Text to split

        Returns:
            List of chunks
        """
        if len(text) <= self.chunk_size:
            return [Chunk(index=0, text=text, start_offset=0, end_offset=len(text))]

        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._split_fixed(text)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._split_sentences(text)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._split_paragraphs(text)
        elif self.strategy == ChunkingStrategy.SECTION:
            return self._split_sections(text)
        elif self.strategy == ChunkingStrategy.RECURSIVE:
            return self._split_recursive(text)
        else:
            return self._split_fixed(text)

    def _split_fixed(self, text: str) -> list[Chunk]:
        """Split into fixed-size chunks with overlap."""
        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to end at a sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start + self.min_chunk_size, end)
                if last_period > start:
                    end = last_period + 1

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(
                    Chunk(
                        index=index,
                        text=chunk_text,
                        start_offset=start,
                        end_offset=end,
                    )
                )
                index += 1

            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    def _split_sentences(self, text: str) -> list[Chunk]:
        """Split on sentence boundaries."""
        sentences = self._sentence_pattern.split(text)
        return self._merge_small_chunks(sentences, text)

    def _split_paragraphs(self, text: str) -> list[Chunk]:
        """Split on paragraph boundaries."""
        paragraphs = self._paragraph_pattern.split(text)
        return self._merge_small_chunks(paragraphs, text)

    def _split_sections(self, text: str) -> list[Chunk]:
        """Split on section headers."""
        sections = self._section_pattern.split(text)
        return self._merge_small_chunks(sections, text)

    def _split_recursive(self, text: str) -> list[Chunk]:
        """Recursively split using multiple strategies.

        Start with sections, then paragraphs, then sentences, then fixed.
        """
        # First, try sections
        sections = self._section_pattern.split(text)
        if len(sections) > 1:
            chunks = []
            for section in sections:
                if len(section) > self.chunk_size:
                    chunks.extend(self._split_recursive_inner(section, level=1))
                elif len(section.strip()) >= self.min_chunk_size:
                    chunks.append(section)
            return self._create_chunks_with_offsets(chunks, text)

        return self._split_recursive_inner(text, level=0)

    def _split_recursive_inner(self, text: str, level: int) -> list[str]:
        """Inner recursive splitting."""
        if len(text) <= self.chunk_size:
            return [text] if len(text.strip()) >= self.min_chunk_size else []

        if level == 0:
            # Try sections
            parts = self._section_pattern.split(text)
        elif level == 1:
            # Try paragraphs
            parts = self._paragraph_pattern.split(text)
        elif level == 2:
            # Try sentences
            parts = self._sentence_pattern.split(text)
        else:
            # Fall back to fixed size
            return [c.text for c in self._split_fixed(text)]

        if len(parts) <= 1:
            return self._split_recursive_inner(text, level + 1)

        result = []
        for part in parts:
            if len(part) > self.chunk_size:
                result.extend(self._split_recursive_inner(part, level + 1))
            elif len(part.strip()) >= self.min_chunk_size:
                result.append(part)

        return result

    def _merge_small_chunks(self, parts: list[str], original_text: str) -> list[Chunk]:
        """Merge small parts into larger chunks."""
        chunks = []
        current_text = ""
        current_start = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(current_text) + len(part) + 1 <= self.chunk_size:
                if current_text:
                    current_text += "\n\n" + part
                else:
                    current_text = part
                    current_start = original_text.find(part)
            else:
                if current_text and len(current_text) >= self.min_chunk_size:
                    chunks.append(
                        Chunk(
                            index=len(chunks),
                            text=current_text,
                            start_offset=current_start,
                            end_offset=current_start + len(current_text),
                        )
                    )
                current_text = part
                current_start = original_text.find(part)

        # Add last chunk
        if current_text and len(current_text) >= self.min_chunk_size:
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=current_text,
                    start_offset=current_start,
                    end_offset=current_start + len(current_text),
                )
            )

        return chunks

    def _create_chunks_with_offsets(
        self, texts: list[str], original_text: str
    ) -> list[Chunk]:
        """Create chunks with offset tracking."""
        chunks = []
        search_start = 0

        for i, text in enumerate(texts):
            text = text.strip()
            if len(text) < self.min_chunk_size:
                continue

            start = original_text.find(text, search_start)
            if start == -1:
                start = search_start

            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=text,
                    start_offset=start,
                    end_offset=start + len(text),
                )
            )
            search_start = start + len(text)

        return chunks

    def get_token_estimate(self, chunk: Chunk) -> int:
        """Estimate token count for a chunk."""
        # Rough estimate: ~4 chars per token
        return len(chunk.text) // 4
