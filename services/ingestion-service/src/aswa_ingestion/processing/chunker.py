"""Text chunking for document processing."""

import re
from typing import TYPE_CHECKING, Any

import tiktoken
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

if TYPE_CHECKING:
    from aswa_ingestion.processing.embedder import EmbeddingClient
    from aswa_ingestion.processing.parser import ParsedDocument

logger = get_logger(__name__)


class TextChunk(BaseModel):
    """A chunk of text with metadata."""

    content: str
    token_count: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextChunker:
    """Split text into chunks suitable for embedding.

    Uses tiktoken for accurate token counting and supports
    sentence-boundary-aware chunking.
    """

    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        tokenizer: str = "cl100k_base",
    ) -> None:
        """Initialize text chunker.

        Args:
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Token overlap between chunks
            tokenizer: Tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(tokenizer)

        logger.debug(
            f"TextChunker initialized: chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}, tokenizer={tokenizer}"
        )

    def chunk(
        self,
        text: str,
        preserve_sentences: bool = True,
    ) -> list[TextChunk]:
        """Split text into overlapping chunks.

        Args:
            text: Input text to chunk
            preserve_sentences: Try to break at sentence boundaries

        Returns:
            List of TextChunk with content, token_count, positions
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        if preserve_sentences:
            return self._chunk_by_sentences(text)
        else:
            return self._chunk_by_tokens(text)

    def chunk_with_metadata(
        self,
        parsed_doc: "ParsedDocument",
    ) -> list[TextChunk]:
        """Chunk document preserving element boundaries where possible.

        Args:
            parsed_doc: ParsedDocument from parser

        Returns:
            List of TextChunk with element type metadata
        """
        chunks: list[TextChunk] = []
        current_position = 0

        # Group elements into logical sections
        sections = self._group_elements_into_sections(parsed_doc)

        for section in sections:
            section_text = section["text"]
            section_metadata = section["metadata"]

            # Chunk this section
            section_chunks = self.chunk(section_text, preserve_sentences=True)

            # Add section metadata to chunks
            for chunk in section_chunks:
                # Adjust positions to global document positions
                chunk.start_char += current_position
                chunk.end_char += current_position
                chunk.metadata.update(section_metadata)
                chunks.append(chunk)

            # Update position (account for separator)
            current_position += len(section_text) + 2  # +2 for "\n\n"

        logger.info(f"Created {len(chunks)} chunks from parsed document")
        return chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Input text

        Returns:
            Token count
        """
        return len(self.encoding.encode(text))

    def _chunk_by_sentences(self, text: str) -> list[TextChunk]:
        """Chunk text respecting sentence boundaries.

        Args:
            text: Input text

        Returns:
            List of chunks
        """
        chunks: list[TextChunk] = []

        # Split into sentences
        sentences = self.SENTENCE_ENDINGS.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        current_chunk_sentences: list[str] = []
        current_tokens = 0
        chunk_start = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # If single sentence exceeds chunk size, split it
            if sentence_tokens > self.chunk_size:
                # First, finalize current chunk if any
                if current_chunk_sentences:
                    chunk = self._create_chunk(
                        " ".join(current_chunk_sentences),
                        chunk_start,
                        text,
                    )
                    chunks.append(chunk)
                    current_chunk_sentences = []
                    current_tokens = 0

                # Split the long sentence
                sub_chunks = self._chunk_by_tokens(sentence)
                for i, sub_chunk in enumerate(sub_chunks):
                    # Adjust positions
                    offset = text.find(sentence, chunk_start)
                    if offset >= 0:
                        sub_chunk.start_char = offset + sub_chunk.start_char
                        sub_chunk.end_char = offset + sub_chunk.end_char
                    chunks.append(sub_chunk)

                chunk_start = chunks[-1].end_char if chunks else 0
                continue

            # Check if adding this sentence exceeds limit
            new_tokens = current_tokens + sentence_tokens + (
                1 if current_chunk_sentences else 0
            )

            if new_tokens > self.chunk_size and current_chunk_sentences:
                # Create chunk from accumulated sentences
                chunk = self._create_chunk(
                    " ".join(current_chunk_sentences),
                    chunk_start,
                    text,
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk_sentences
                )
                current_chunk_sentences = overlap_sentences + [sentence]
                current_tokens = sum(
                    self.count_tokens(s) for s in current_chunk_sentences
                )
                chunk_start = chunk.end_char - len(" ".join(overlap_sentences))
            else:
                current_chunk_sentences.append(sentence)
                current_tokens = new_tokens

        # Final chunk
        if current_chunk_sentences:
            chunk = self._create_chunk(
                " ".join(current_chunk_sentences),
                chunk_start,
                text,
            )
            chunks.append(chunk)

        return chunks

    def _chunk_by_tokens(self, text: str) -> list[TextChunk]:
        """Chunk text by token count without sentence awareness.

        Args:
            text: Input text

        Returns:
            List of chunks
        """
        chunks: list[TextChunk] = []
        tokens = self.encoding.encode(text)

        if not tokens:
            return []

        start_idx = 0
        while start_idx < len(tokens):
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.encoding.decode(chunk_tokens)

            # Calculate character positions
            if chunks:
                start_char = chunks[-1].end_char - self._overlap_chars(text, chunks[-1])
            else:
                start_char = 0

            # Find actual position in text
            start_char = max(0, text.find(chunk_text[:50], max(0, start_char - 10)))
            end_char = start_char + len(chunk_text)

            chunks.append(
                TextChunk(
                    content=chunk_text,
                    token_count=len(chunk_tokens),
                    start_char=start_char,
                    end_char=end_char,
                )
            )

            # Move to next position with overlap
            start_idx = end_idx - self.chunk_overlap

            # Prevent infinite loop
            if start_idx >= end_idx:
                start_idx = end_idx

        return chunks

    def _create_chunk(
        self,
        content: str,
        search_start: int,
        full_text: str,
    ) -> TextChunk:
        """Create a TextChunk with accurate positions.

        Args:
            content: Chunk content
            search_start: Position to start searching from
            full_text: Full document text

        Returns:
            TextChunk instance
        """
        # Find content in full text
        start_char = full_text.find(content, max(0, search_start - 10))
        if start_char < 0:
            start_char = search_start

        end_char = start_char + len(content)

        return TextChunk(
            content=content,
            token_count=self.count_tokens(content),
            start_char=start_char,
            end_char=end_char,
        )

    def _get_overlap_sentences(
        self,
        sentences: list[str],
    ) -> list[str]:
        """Get sentences for overlap.

        Args:
            sentences: List of sentences

        Returns:
            Sentences to include in overlap
        """
        if not sentences:
            return []

        overlap_tokens = 0
        overlap_sentences: list[str] = []

        # Work backwards through sentences
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)
            if overlap_tokens + sentence_tokens <= self.chunk_overlap:
                overlap_sentences.insert(0, sentence)
                overlap_tokens += sentence_tokens
            else:
                break

        return overlap_sentences

    def _overlap_chars(self, text: str, prev_chunk: TextChunk) -> int:
        """Calculate overlap character count.

        Args:
            text: Full text
            prev_chunk: Previous chunk

        Returns:
            Number of characters of overlap
        """
        # Estimate based on token ratio
        if prev_chunk.token_count == 0:
            return 0

        chars_per_token = len(prev_chunk.content) / prev_chunk.token_count
        return int(self.chunk_overlap * chars_per_token)

    def _group_elements_into_sections(
        self,
        parsed_doc: "ParsedDocument",
    ) -> list[dict[str, Any]]:
        """Group document elements into logical sections.

        Args:
            parsed_doc: Parsed document

        Returns:
            List of sections with text and metadata
        """
        sections: list[dict[str, Any]] = []
        current_section: dict[str, Any] = {
            "text": "",
            "metadata": {"element_types": []},
        }

        for element in parsed_doc.elements:
            # Start new section on title
            if element.type == "title" and current_section["text"]:
                sections.append(current_section)
                current_section = {
                    "text": element.text,
                    "metadata": {
                        "element_types": [element.type],
                        "page_number": element.page_number,
                    },
                }
            else:
                # Add to current section
                if current_section["text"]:
                    current_section["text"] += "\n\n" + element.text
                else:
                    current_section["text"] = element.text

                if element.type not in current_section["metadata"]["element_types"]:
                    current_section["metadata"]["element_types"].append(element.type)

                if element.page_number is not None:
                    current_section["metadata"]["page_number"] = element.page_number

        # Add final section
        if current_section["text"]:
            sections.append(current_section)

        return sections


class SemanticChunker(TextChunker):
    """Advanced chunker that uses semantic similarity to find chunk boundaries.

    Finds natural break points where semantic content shifts significantly.
    """

    def __init__(
        self,
        embedding_client: "EmbeddingClient",
        similarity_threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        """Initialize semantic chunker.

        Args:
            embedding_client: Client for generating embeddings
            similarity_threshold: Cosine similarity threshold for breaks
            **kwargs: Arguments passed to TextChunker
        """
        super().__init__(**kwargs)
        self.embedding_client = embedding_client
        self.similarity_threshold = similarity_threshold

    async def chunk_semantic(self, text: str) -> list[TextChunk]:
        """Split text at semantic boundaries.

        Uses embeddings to find points where content meaning
        shifts significantly.

        Args:
            text: Input text

        Returns:
            List of semantically coherent chunks
        """
        if not text or not text.strip():
            return []

        # First split into sentences
        sentences = self.SENTENCE_ENDINGS.split(text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return self.chunk(text, preserve_sentences=False)

        logger.debug(f"Computing embeddings for {len(sentences)} sentences")

        # Get embeddings for all sentences
        embeddings = await self.embedding_client.embed_batch(sentences)

        # Find semantic break points
        break_points = self._find_semantic_breaks(embeddings)

        # Create chunks based on break points
        chunks: list[TextChunk] = []
        current_start = 0
        current_position = 0

        for i, sentence in enumerate(sentences):
            if i in break_points or i == len(sentences) - 1:
                # End of chunk
                chunk_sentences = sentences[current_start : i + 1]
                chunk_text = " ".join(chunk_sentences)

                # Find position in original text
                start_char = text.find(chunk_sentences[0], current_position)
                if start_char < 0:
                    start_char = current_position
                end_char = start_char + len(chunk_text)

                chunks.append(
                    TextChunk(
                        content=chunk_text,
                        token_count=self.count_tokens(chunk_text),
                        start_char=start_char,
                        end_char=end_char,
                        metadata={"semantic_break": True},
                    )
                )

                current_start = i + 1
                current_position = end_char

        logger.info(f"Created {len(chunks)} semantic chunks")
        return chunks

    def _find_semantic_breaks(
        self,
        embeddings: list[list[float]],
    ) -> set[int]:
        """Find indices where semantic content shifts.

        Args:
            embeddings: List of sentence embeddings

        Returns:
            Set of indices that are semantic break points
        """
        break_points: set[int] = set()

        for i in range(len(embeddings) - 1):
            similarity = self._cosine_similarity(embeddings[i], embeddings[i + 1])

            if similarity < self.similarity_threshold:
                break_points.add(i)

        return break_points

    def _cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score
        """
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
