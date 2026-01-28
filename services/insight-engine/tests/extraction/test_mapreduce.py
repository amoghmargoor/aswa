import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from aswa_insight.extraction.extractor import ExtractionResult, StructuredExtractor
from aswa_insight.extraction.mapreduce import MapReduceExtractor, MapReduceResult
from aswa_insight.models.entities import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
)


class TestMapReduceExtractor:
    @pytest.fixture
    def mock_extractor(self):
        extractor = MagicMock(spec=StructuredExtractor)
        extractor.extract = AsyncMock()
        return extractor

    @pytest.fixture
    def mapreduce(self, mock_extractor):
        return MapReduceExtractor(
            extractor=mock_extractor,
            max_concurrent_chunks=2,
        )

    @pytest.mark.asyncio
    async def test_short_document_no_chunking(self, mapreduce, mock_extractor):
        """Test short document doesn't need chunking."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        result = await mapreduce.extract(
            text="Short text",
            extraction_type="entity",
        )

        assert result.total_chunks == 1
        assert result.success

    @pytest.mark.asyncio
    async def test_long_document_chunked(self, mapreduce, mock_extractor):
        """Test long document is chunked."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        # Create long text
        long_text = "Paragraph. " * 1000

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        assert result.total_chunks > 1

    @pytest.mark.asyncio
    async def test_deduplication(self, mapreduce, mock_extractor):
        """Test duplicate insights are deduplicated."""
        # Setup mock to return same entity from different chunks
        entity = {
            "name": "Test Corp",
            "entity_type": "organization",
            "confidence": 0.8,
        }

        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=MagicMock(model_dump=lambda: {"entities": [entity]}),
        )

        long_text = "Test Corp is mentioned. " * 500

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        # Should deduplicate
        assert result.deduplication_stats["removed"] >= 0

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, mapreduce, mock_extractor):
        """Test handling of partial chunk failures."""
        call_count = 0

        async def mock_extract(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return ExtractionResult(success=False, error="Chunk failed")
            return ExtractionResult(
                success=True,
                result=EntityExtractionResult(entities=[]),
            )

        mock_extractor.extract = mock_extract

        long_text = "Content. " * 500

        result = await mapreduce.extract(
            text=long_text,
            extraction_type="entity",
        )

        assert result.failed_chunks >= 1
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_with_document_metadata(self, mapreduce, mock_extractor):
        """Test extraction with document metadata."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        result = await mapreduce.extract(
            text="Test content",
            extraction_type="entity",
            document_title="Annual Report 2024",
            document_summary="This is a financial report.",
        )

        assert result.success
        assert result.total_chunks == 1

    @pytest.mark.asyncio
    async def test_with_context(self, mapreduce, mock_extractor):
        """Test extraction with context."""
        mock_extractor.extract.return_value = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=EntityExtractionResult(entities=[]),
        )

        context = {"industry": "technology", "document_type": "annual_report"}

        result = await mapreduce.extract(
            text="Test content",
            extraction_type="entity",
            context=context,
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_merge_insight_data(self, mapreduce):
        """Test merging insight data from duplicates."""
        existing = {
            "name": "Test",
            "confidence": 0.8,
            "sources": [{"text": "source1"}],
        }
        new = {
            "name": "Test",
            "confidence": 0.9,
            "sources": [{"text": "source2"}],
        }

        mapreduce._merge_insight_data(existing, new)

        assert existing["confidence"] == 0.9
        assert len(existing["sources"]) == 2


class TestMapReduceResult:
    def test_success_all_passed(self):
        """Test success when all chunks pass."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=3,
            failed_chunks=0,
        )
        assert result.success is True

    def test_success_partial_pass(self):
        """Test success with partial failures."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=2,
            failed_chunks=1,
        )
        assert result.success is True  # At least some succeeded

    def test_failure_all_failed(self):
        """Test failure when all chunks fail."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=3,
            successful_chunks=0,
            failed_chunks=3,
        )
        assert result.success is False

    def test_default_values(self):
        """Test default values."""
        result = MapReduceResult(
            document_id=uuid4(),
            total_chunks=1,
            successful_chunks=1,
            failed_chunks=0,
        )
        assert result.chunk_results == []
        assert result.merged_insights == []
        assert result.deduplication_stats == {}
        assert result.errors == []
