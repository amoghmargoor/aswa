import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.extraction.processor import ExtractionProcessor, ProcessingResult
from aswa_insight.extraction.extractor import ExtractionResult, StructuredExtractor
from aswa_insight.extraction.validators import ExtractionValidator, ValidationResult
from aswa_insight.models.entities import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
)
from aswa_insight.models.insights import InsightType


class TestExtractionProcessor:
    @pytest.fixture
    def mock_extractor(self):
        extractor = MagicMock(spec=StructuredExtractor)
        extractor.extract_all = AsyncMock()
        return extractor

    @pytest.fixture
    def processor(self, mock_extractor):
        return ExtractionProcessor(
            extractor=mock_extractor,
            extraction_types=["entity"],
        )

    @pytest.mark.asyncio
    async def test_process_document_success(self, processor, mock_extractor):
        """Test successful document processing."""
        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=True,
                extraction_type="entity",
                result=EntityExtractionResult(
                    entities=[
                        ExtractedEntity(
                            name="Test Corp",
                            entity_type=EntityType.ORGANIZATION,
                            description="A company",
                            confidence=0.9,
                        )
                    ]
                ),
            )
        }

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Test Corp is a company.",
        )

        assert result.success is True
        assert result.insight_count >= 1
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_process_document_with_errors(self, processor, mock_extractor):
        """Test processing with extraction errors."""
        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=False,
                extraction_type="entity",
                error="Extraction failed",
            )
        }

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Some text",
        )

        assert result.success is False
        assert len(result.errors) > 0
        assert "Extraction failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_process_document_with_context(self, processor, mock_extractor):
        """Test processing with context."""
        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=True,
                extraction_type="entity",
                result=EntityExtractionResult(entities=[]),
            )
        }

        context = {"document_type": "annual_report"}

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Test text",
            context=context,
        )

        # Verify context was passed to extractor
        mock_extractor.extract_all.assert_called_once()
        call_kwargs = mock_extractor.extract_all.call_args.kwargs
        assert call_kwargs["context"] == context

    @pytest.mark.asyncio
    async def test_process_document_custom_types(self, processor, mock_extractor):
        """Test processing with custom extraction types."""
        mock_extractor.extract_all.return_value = {
            "risk": ExtractionResult(
                success=True,
                extraction_type="risk",
                result=MagicMock(),
            )
        }

        await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Test text",
            extraction_types=["risk"],
        )

        call_kwargs = mock_extractor.extract_all.call_args.kwargs
        assert call_kwargs["extraction_types"] == ["risk"]

    @pytest.mark.asyncio
    async def test_process_document_creates_insights(self, processor, mock_extractor):
        """Test that processing creates insights from entities."""
        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=True,
                extraction_type="entity",
                result=EntityExtractionResult(
                    entities=[
                        ExtractedEntity(
                            name="Company A",
                            entity_type=EntityType.ORGANIZATION,
                            description="First company",
                            confidence=0.8,
                        ),
                        ExtractedEntity(
                            name="Company B",
                            entity_type=EntityType.ORGANIZATION,
                            description="Second company",
                            confidence=0.7,
                        ),
                    ]
                ),
            )
        }

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Test text",
        )

        assert result.insight_count == 2
        assert all(i.insight_type == InsightType.ENTITY for i in result.insights)
        assert any(i.title == "Company A" for i in result.insights)
        assert any(i.title == "Company B" for i in result.insights)

    @pytest.mark.asyncio
    async def test_process_document_validation_failure(self, mock_extractor):
        """Test that invalid extractions are not converted to insights."""
        # Create validator that requires higher confidence
        validator = ExtractionValidator(min_confidence=0.9)
        processor = ExtractionProcessor(
            extractor=mock_extractor,
            validator=validator,
            extraction_types=["entity"],
        )

        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=True,
                extraction_type="entity",
                result=EntityExtractionResult(
                    entities=[
                        ExtractedEntity(
                            name="Low Confidence",
                            entity_type=EntityType.ORGANIZATION,
                            description="Test",
                            confidence=0.5,  # Below min
                        )
                    ]
                ),
            )
        }

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="Test text",
        )

        # Extraction succeeded but entity was filtered out due to low confidence
        assert result.success is True
        # The cleaned data will have 0 entities after filtering
        assert result.insight_count == 0

    @pytest.mark.asyncio
    async def test_process_document_includes_quality(self, processor, mock_extractor):
        """Test that document quality is assessed."""
        mock_extractor.extract_all.return_value = {
            "entity": ExtractionResult(
                success=True,
                extraction_type="entity",
                result=EntityExtractionResult(entities=[]),
            )
        }

        result = await processor.process_document(
            document_id=uuid4(),
            tenant_id=uuid4(),
            text="This is a test document with some content.",
        )

        assert result.document_quality is not None
        assert result.document_quality.word_count > 0


class TestProcessingResult:
    def test_success_property(self):
        """Test success property calculation."""
        result = ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={"entity": ExtractionResult(success=True)},
            validation_results={},
            insights=[],
        )
        assert result.success is True

    def test_success_false_with_errors(self):
        """Test success is False when errors present."""
        result = ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={"entity": ExtractionResult(success=True)},
            validation_results={},
            insights=[],
            errors=["Some error"],
        )
        assert result.success is False

    def test_success_false_with_failed_extraction(self):
        """Test success is False when extraction failed."""
        result = ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={"entity": ExtractionResult(success=False)},
            validation_results={},
            insights=[],
        )
        assert result.success is False

    def test_insight_count(self):
        """Test insight count property."""
        from aswa_insight.models.insights import Insight, InsightType

        result = ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={},
            validation_results={},
            insights=[
                Insight(
                    tenant_id=uuid4(),
                    document_id=uuid4(),
                    insight_type=InsightType.ENTITY,
                    title="Test",
                    description="Test",
                    confidence=0.8,
                ),
                Insight(
                    tenant_id=uuid4(),
                    document_id=uuid4(),
                    insight_type=InsightType.ENTITY,
                    title="Test 2",
                    description="Test 2",
                    confidence=0.7,
                ),
            ],
        )
        assert result.insight_count == 2

    def test_empty_errors_by_default(self):
        """Test errors list is empty by default."""
        result = ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={},
            validation_results={},
            insights=[],
        )
        assert result.errors == []
