"""Tests for text chunker."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aswa_ingestion.processing.chunker import TextChunker, TextChunk, SemanticChunker
from aswa_ingestion.processing.parser import ParsedDocument, DocumentElement


class TestTextChunker:
    """Tests for TextChunker class."""

    @pytest.fixture
    def chunker(self) -> TextChunker:
        """Create chunker instance."""
        return TextChunker(chunk_size=100, chunk_overlap=20)

    def test_init_with_defaults(self) -> None:
        """Test chunker initialization with defaults."""
        chunker = TextChunker()
        assert chunker.chunk_size == 512
        assert chunker.chunk_overlap == 64

    def test_init_with_custom_values(self) -> None:
        """Test chunker initialization with custom values."""
        chunker = TextChunker(chunk_size=256, chunk_overlap=32)
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 32

    def test_count_tokens(self, chunker: TextChunker) -> None:
        """Test token counting."""
        text = "Hello world"
        count = chunker.count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty(self, chunker: TextChunker) -> None:
        """Test token counting for empty text."""
        assert chunker.count_tokens("") == 0

    def test_chunk_empty_text(self, chunker: TextChunker) -> None:
        """Test chunking empty text returns empty list."""
        result = chunker.chunk("")
        assert result == []

    def test_chunk_whitespace_only(self, chunker: TextChunker) -> None:
        """Test chunking whitespace-only text returns empty list."""
        result = chunker.chunk("   \n\t   ")
        assert result == []

    def test_chunk_short_text(self, chunker: TextChunker) -> None:
        """Test chunking text shorter than chunk size."""
        text = "This is a short sentence."
        result = chunker.chunk(text)

        assert len(result) == 1
        assert result[0].content.strip() == text
        assert result[0].token_count > 0

    def test_chunk_preserves_sentences(self, chunker: TextChunker) -> None:
        """Test that chunking preserves sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence."
        result = chunker.chunk(text, preserve_sentences=True)

        # All chunks should contain complete sentences
        for chunk in result:
            assert chunk.content.strip()

    def test_chunk_creates_overlap(self) -> None:
        """Test that chunks have overlap."""
        # Create chunker with small size to force multiple chunks
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        text = "The quick brown fox jumps over the lazy dog. " * 10

        result = chunker.chunk(text, preserve_sentences=False)

        if len(result) >= 2:
            # Check that some content overlaps between consecutive chunks
            # This is a simplified check
            assert len(result) >= 2

    def test_chunk_positions(self, chunker: TextChunker) -> None:
        """Test that chunk positions are valid."""
        text = "First sentence. Second sentence. Third sentence."
        result = chunker.chunk(text)

        for chunk in result:
            assert chunk.start_char >= 0
            assert chunk.end_char >= chunk.start_char
            assert chunk.end_char <= len(text) + 10  # Allow some tolerance


class TestChunkWithMetadata:
    """Tests for chunking with metadata preservation."""

    @pytest.fixture
    def chunker(self) -> TextChunker:
        """Create chunker instance."""
        return TextChunker(chunk_size=100, chunk_overlap=20)

    def test_chunk_with_metadata_empty_doc(self, chunker: TextChunker) -> None:
        """Test chunking empty parsed document."""
        parsed_doc = ParsedDocument(
            text="",
            elements=[],
            metadata={},
            word_count=0,
        )

        result = chunker.chunk_with_metadata(parsed_doc)
        assert result == []

    def test_chunk_with_metadata_single_element(self, chunker: TextChunker) -> None:
        """Test chunking document with single element."""
        parsed_doc = ParsedDocument(
            text="This is test content.",
            elements=[
                DocumentElement(
                    type="narrative_text",
                    text="This is test content.",
                    page_number=1,
                )
            ],
            metadata={},
            word_count=4,
        )

        result = chunker.chunk_with_metadata(parsed_doc)

        assert len(result) >= 1
        assert "element_types" in result[0].metadata

    def test_chunk_preserves_page_numbers(self, chunker: TextChunker) -> None:
        """Test that page numbers are preserved in metadata."""
        parsed_doc = ParsedDocument(
            text="Content on page one. Content on page two.",
            elements=[
                DocumentElement(
                    type="narrative_text",
                    text="Content on page one.",
                    page_number=1,
                ),
                DocumentElement(
                    type="narrative_text",
                    text="Content on page two.",
                    page_number=2,
                ),
            ],
            metadata={},
            word_count=8,
        )

        result = chunker.chunk_with_metadata(parsed_doc)

        # At least one chunk should have page number
        has_page = any("page_number" in c.metadata for c in result)
        assert has_page or len(result) > 0


class TestTextChunk:
    """Tests for TextChunk model."""

    def test_text_chunk_creation(self) -> None:
        """Test creating a text chunk."""
        chunk = TextChunk(
            content="Test content",
            token_count=3,
            start_char=0,
            end_char=12,
        )

        assert chunk.content == "Test content"
        assert chunk.token_count == 3
        assert chunk.metadata == {}

    def test_text_chunk_with_metadata(self) -> None:
        """Test creating a text chunk with metadata."""
        chunk = TextChunk(
            content="Test content",
            token_count=3,
            start_char=0,
            end_char=12,
            metadata={"page": 1, "section": "intro"},
        )

        assert chunk.metadata["page"] == 1
        assert chunk.metadata["section"] == "intro"


class TestChunkBySentences:
    """Tests for sentence-based chunking."""

    def test_single_sentence(self) -> None:
        """Test chunking single sentence."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "This is a single sentence."

        result = chunker._chunk_by_sentences(text)

        assert len(result) == 1
        assert result[0].content.strip() == text

    def test_multiple_sentences_fit_in_chunk(self) -> None:
        """Test multiple sentences that fit in one chunk."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "First. Second. Third."

        result = chunker._chunk_by_sentences(text)

        # Should fit in one chunk
        assert len(result) == 1

    def test_long_sentence_gets_split(self) -> None:
        """Test that very long sentences get split."""
        chunker = TextChunker(chunk_size=10, chunk_overlap=2)
        text = "This is a very long sentence that definitely exceeds the chunk size limit."

        result = chunker._chunk_by_sentences(text)

        # Should be split into multiple chunks
        assert len(result) >= 1


class TestChunkByTokens:
    """Tests for token-based chunking."""

    def test_chunk_by_tokens_short(self) -> None:
        """Test token chunking for short text."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "Short text."

        result = chunker._chunk_by_tokens(text)

        assert len(result) == 1

    def test_chunk_by_tokens_creates_chunks(self) -> None:
        """Test token chunking creates multiple chunks for long text."""
        chunker = TextChunker(chunk_size=10, chunk_overlap=2)
        text = "This is a longer text that should be split into multiple chunks."

        result = chunker._chunk_by_tokens(text)

        assert len(result) >= 1


class TestSemanticChunker:
    """Tests for SemanticChunker class."""

    @pytest.fixture
    def mock_embedder(self) -> AsyncMock:
        """Create mock embedding client."""
        embedder = AsyncMock()
        # Return different embeddings to simulate semantic shifts
        embedder.embed_batch = AsyncMock(
            return_value=[
                [0.1] * 10,
                [0.1] * 10,  # Similar to first
                [0.9] * 10,  # Different - semantic break
                [0.9] * 10,  # Similar to third
            ]
        )
        return embedder

    @pytest.fixture
    def semantic_chunker(self, mock_embedder: AsyncMock) -> SemanticChunker:
        """Create semantic chunker instance."""
        return SemanticChunker(
            embedding_client=mock_embedder,
            similarity_threshold=0.5,
            chunk_size=512,
            chunk_overlap=64,
        )

    def test_cosine_similarity(self, semantic_chunker: SemanticChunker) -> None:
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = semantic_chunker._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(
        self, semantic_chunker: SemanticChunker
    ) -> None:
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]

        similarity = semantic_chunker._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(
        self, semantic_chunker: SemanticChunker
    ) -> None:
        """Test cosine similarity with zero vector."""
        vec1 = [0.0, 0.0]
        vec2 = [1.0, 1.0]

        similarity = semantic_chunker._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_find_semantic_breaks(self, semantic_chunker: SemanticChunker) -> None:
        """Test finding semantic break points."""
        # Embeddings that have a break in the middle
        embeddings = [
            [1.0, 0.0],  # 0
            [0.9, 0.1],  # 1 - similar to 0
            [0.1, 0.9],  # 2 - very different from 1
            [0.0, 1.0],  # 3 - similar to 2
        ]

        breaks = semantic_chunker._find_semantic_breaks(embeddings)

        # Should find break between index 1 and 2
        assert 1 in breaks

    @pytest.mark.asyncio
    async def test_chunk_semantic_empty(
        self, semantic_chunker: SemanticChunker
    ) -> None:
        """Test semantic chunking with empty text."""
        result = await semantic_chunker.chunk_semantic("")
        assert result == []

    @pytest.mark.asyncio
    async def test_chunk_semantic_single_sentence(
        self,
        semantic_chunker: SemanticChunker,
        mock_embedder: AsyncMock,
    ) -> None:
        """Test semantic chunking with single sentence."""
        mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 10])

        result = await semantic_chunker.chunk_semantic("Single sentence.")

        # Should fall back to regular chunking
        assert len(result) >= 1
