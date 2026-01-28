import pytest

from aswa_insight.chunking.splitter import Chunk, ChunkingStrategy, TextSplitter


class TestTextSplitter:
    def test_short_text_single_chunk(self):
        """Test short text returns single chunk."""
        splitter = TextSplitter(chunk_size=1000)
        text = "This is a short text."
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_fixed_size_chunking(self):
        """Test fixed size chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=100,
            chunk_overlap=20,
        )
        text = "A" * 500
        chunks = splitter.split(text)
        assert len(chunks) > 1
        # Check overlap
        assert chunks[0].end_offset > chunks[1].start_offset

    def test_sentence_chunking(self):
        """Test sentence-based chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=100,
        )
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = splitter.split(text)
        # Should split on sentence boundaries
        for chunk in chunks:
            assert chunk.text.endswith(".") or chunk.text.endswith("...")

    def test_paragraph_chunking(self):
        """Test paragraph-based chunking."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=200,
        )
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_recursive_chunking(self):
        """Test recursive chunking strategy."""
        splitter = TextSplitter(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=200,
        )
        text = "# Section 1\n\nParagraph 1.\n\n# Section 2\n\nParagraph 2."
        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_chunk_offsets_correct(self):
        """Test chunk offsets are correct."""
        splitter = TextSplitter(chunk_size=100)
        text = "A" * 300
        chunks = splitter.split(text)

        for chunk in chunks:
            assert chunk.start_offset >= 0
            assert chunk.end_offset <= len(text)
            assert chunk.start_offset < chunk.end_offset

    def test_min_chunk_size_respected(self):
        """Test minimum chunk size is respected."""
        splitter = TextSplitter(
            chunk_size=100,
            min_chunk_size=50,
        )
        text = "Short.\n\n" + "A" * 200
        chunks = splitter.split(text)

        for chunk in chunks:
            assert len(chunk.text) >= splitter.min_chunk_size

    def test_token_estimate(self):
        """Test token estimation."""
        splitter = TextSplitter()
        chunk = Chunk(
            index=0,
            text="Hello world this is a test",
            start_offset=0,
            end_offset=26,
        )
        estimate = splitter.get_token_estimate(chunk)
        # ~4 chars per token, 26 chars = ~6 tokens
        assert estimate > 0
        assert estimate < len(chunk.text)


class TestChunk:
    def test_chunk_properties(self):
        """Test chunk properties."""
        chunk = Chunk(
            index=0,
            text="Hello world test",
            start_offset=0,
            end_offset=16,
        )
        assert chunk.length == 16
        assert chunk.word_count == 3

    def test_chunk_metadata(self):
        """Test chunk metadata."""
        chunk = Chunk(
            index=0,
            text="Test",
            start_offset=0,
            end_offset=4,
            metadata={"key": "value"},
        )
        assert chunk.metadata["key"] == "value"
