import pytest

from aswa_insight.chunking.context import ChunkContext, ChunkContextBuilder
from aswa_insight.chunking.splitter import Chunk


class TestChunkContextBuilder:
    def test_build_single_chunk_context(self):
        """Test context for single chunk."""
        builder = ChunkContextBuilder()
        chunks = [Chunk(index=0, text="Test content", start_offset=0, end_offset=12)]

        contexts = builder.build_contexts(chunks, document_title="Test Doc")

        assert len(contexts) == 1
        assert contexts[0].document_title == "Test Doc"
        assert "Entire document" in contexts[0].position_description

    def test_build_multiple_chunk_contexts(self):
        """Test context for multiple chunks."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(index=0, text="First chunk", start_offset=0, end_offset=11),
            Chunk(index=1, text="Second chunk", start_offset=11, end_offset=23),
            Chunk(index=2, text="Third chunk", start_offset=23, end_offset=34),
        ]

        contexts = builder.build_contexts(chunks)

        assert len(contexts) == 3
        assert "Beginning" in contexts[0].position_description
        assert "Middle" in contexts[1].position_description
        assert "End" in contexts[2].position_description

    def test_previous_chunk_summary(self):
        """Test previous chunk summary is included."""
        builder = ChunkContextBuilder(include_previous_summary=True)
        chunks = [
            Chunk(
                index=0, text="First chunk content here.", start_offset=0, end_offset=25
            ),
            Chunk(index=1, text="Second chunk content.", start_offset=25, end_offset=46),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].previous_chunk_summary is None
        assert contexts[1].previous_chunk_summary is not None

    def test_detect_section_title(self):
        """Test section title detection."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(
                index=0,
                text="# Introduction\n\nThis is content.",
                start_offset=0,
                end_offset=30,
            ),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].section_title == "Introduction"

    def test_detect_all_caps_title(self):
        """Test ALL CAPS section title detection."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(
                index=0,
                text="EXECUTIVE SUMMARY\n\nThis is content.",
                start_offset=0,
                end_offset=35,
            ),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].section_title == "EXECUTIVE SUMMARY"

    def test_detect_numbered_title(self):
        """Test numbered section title detection."""
        builder = ChunkContextBuilder()
        chunks = [
            Chunk(
                index=0,
                text="1. Introduction\n\nThis is content.",
                start_offset=0,
                end_offset=33,
            ),
        ]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].section_title == "1. Introduction"

    def test_no_position_when_disabled(self):
        """Test position is not included when disabled."""
        builder = ChunkContextBuilder(include_position=False)
        chunks = [Chunk(index=0, text="Test", start_offset=0, end_offset=4)]

        contexts = builder.build_contexts(chunks)

        assert contexts[0].position_description is None

    def test_no_summary_when_disabled(self):
        """Test document summary is not included when disabled."""
        builder = ChunkContextBuilder(include_document_summary=False)
        chunks = [Chunk(index=0, text="Test", start_offset=0, end_offset=4)]

        contexts = builder.build_contexts(
            chunks, document_summary="This is a summary."
        )

        assert contexts[0].document_summary is None

    def test_metadata_passed_through(self):
        """Test metadata is passed to contexts."""
        builder = ChunkContextBuilder()
        chunks = [Chunk(index=0, text="Test", start_offset=0, end_offset=4)]
        metadata = {"doc_type": "report", "author": "Test"}

        contexts = builder.build_contexts(chunks, metadata=metadata)

        assert contexts[0].metadata == metadata


class TestChunkContext:
    def test_to_context_string(self):
        """Test context string generation."""
        context = ChunkContext(
            chunk=Chunk(index=0, text="Test", start_offset=0, end_offset=4),
            document_title="My Document",
            section_title="Introduction",
            position_description="Beginning",
        )

        context_str = context.to_context_string()

        assert "My Document" in context_str
        assert "Introduction" in context_str
        assert "Beginning" in context_str

    def test_to_context_string_with_summary(self):
        """Test context string includes document summary."""
        context = ChunkContext(
            chunk=Chunk(index=0, text="Test", start_offset=0, end_offset=4),
            document_title="My Document",
            document_summary="This is a test document.",
        )

        context_str = context.to_context_string()

        assert "My Document" in context_str
        assert "This is a test document" in context_str

    def test_to_context_string_empty(self):
        """Test context string when no context is set."""
        context = ChunkContext(
            chunk=Chunk(index=0, text="Test", start_offset=0, end_offset=4),
        )

        context_str = context.to_context_string()

        assert context_str == ""
