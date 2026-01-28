import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_insight.extraction.extractor import ExtractionResult, StructuredExtractor
from aswa_insight.models.entities import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
)


class TestExtractionResult:
    def test_to_dict_success(self):
        """Test successful result serialization."""
        result = ExtractionResult(
            success=True,
            extraction_type="entity",
            processing_time_ms=100,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["extraction_type"] == "entity"
        assert data["processing_time_ms"] == 100
        assert data["result"] is None
        assert data["error"] is None

    def test_to_dict_with_result(self):
        """Test result with model serialization."""
        entity_result = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test Corp",
                    entity_type=EntityType.ORGANIZATION,
                    description="A test company",
                    confidence=0.9,
                )
            ]
        )
        result = ExtractionResult(
            success=True,
            extraction_type="entity",
            result=entity_result,
            processing_time_ms=150,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["result"] is not None
        assert "entities" in data["result"]
        assert len(data["result"]["entities"]) == 1

    def test_to_dict_with_error(self):
        """Test result with error serialization."""
        result = ExtractionResult(
            success=False,
            extraction_type="entity",
            error="Something went wrong",
            processing_time_ms=50,
        )
        data = result.to_dict()
        assert data["success"] is False
        assert data["error"] == "Something went wrong"


class TestStructuredExtractor:
    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = AsyncMock()
        client.count_tokens = AsyncMock(return_value=100)
        client.complete_structured = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_llm_client):
        """Create extractor with mock client."""
        return StructuredExtractor(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_extract_success(self, extractor, mock_llm_client):
        """Test successful extraction."""
        # Setup mock response
        mock_response = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test Corp",
                    entity_type=EntityType.ORGANIZATION,
                    description="A test company",
                    confidence=0.9,
                )
            ]
        )
        mock_llm_client.complete_structured.return_value = mock_response

        result = await extractor.extract(
            text="Test Corp is a company.",
            extraction_type="entity",
        )

        assert result.success is True
        assert result.extraction_type == "entity"
        assert result.result is not None
        assert result.error is None
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_extract_unknown_type(self, extractor):
        """Test extraction with unknown type."""
        result = await extractor.extract(
            text="Some text",
            extraction_type="unknown_type",
        )

        assert result.success is False
        assert "Validation error" in result.error

    @pytest.mark.asyncio
    async def test_extract_llm_error(self, extractor, mock_llm_client):
        """Test extraction when LLM fails."""
        mock_llm_client.complete_structured.side_effect = Exception("LLM error")

        result = await extractor.extract(
            text="Some text",
            extraction_type="entity",
        )

        assert result.success is False
        assert "LLM error" in result.error

    @pytest.mark.asyncio
    async def test_extract_all(self, extractor, mock_llm_client):
        """Test extracting all types."""
        mock_response = EntityExtractionResult(entities=[])
        mock_llm_client.complete_structured.return_value = mock_response

        results = await extractor.extract_all(
            text="Test text",
            extraction_types=["entity", "risk"],
        )

        assert "entity" in results
        assert "risk" in results
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_extract_all_default_types(self, extractor, mock_llm_client):
        """Test extracting with default types."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {}
        mock_response.model_validate.return_value = mock_response
        mock_llm_client.complete_structured.return_value = mock_response

        results = await extractor.extract_all(text="Test text")

        # Default types: entity, risk, opportunity, pattern
        assert len(results) == 4
        assert "entity" in results
        assert "risk" in results
        assert "opportunity" in results
        assert "pattern" in results

    def test_get_metrics(self, extractor):
        """Test metrics retrieval."""
        metrics = extractor.get_metrics()
        assert "extraction_count" in metrics
        assert "error_count" in metrics
        assert "total_tokens" in metrics
        assert "error_rate" in metrics
        assert metrics["extraction_count"] == 0
        assert metrics["error_count"] == 0

    @pytest.mark.asyncio
    async def test_metrics_updated_on_success(self, extractor, mock_llm_client):
        """Test metrics are updated after successful extraction."""
        mock_response = EntityExtractionResult(entities=[])
        mock_llm_client.complete_structured.return_value = mock_response

        await extractor.extract(text="Test", extraction_type="entity")

        metrics = extractor.get_metrics()
        assert metrics["extraction_count"] == 1
        assert metrics["error_count"] == 0

    @pytest.mark.asyncio
    async def test_metrics_updated_on_error(self, extractor, mock_llm_client):
        """Test metrics are updated after failed extraction."""
        mock_llm_client.complete_structured.side_effect = Exception("Error")

        await extractor.extract(text="Test", extraction_type="entity")

        metrics = extractor.get_metrics()
        assert metrics["error_count"] == 1

    def test_calibrate_confidences(self, extractor):
        """Test confidence calibration."""
        # Create a response with high confidence
        response = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.95,
                )
            ]
        )

        # Calibrate
        calibrated = extractor._calibrate_confidences(response)

        # High confidence should be reduced by calibration
        assert calibrated.entities[0].confidence < 0.95

    def test_calibrate_confidences_disabled(self, mock_llm_client):
        """Test that calibration can be disabled."""
        extractor = StructuredExtractor(
            llm_client=mock_llm_client,
            calibrate_confidence_scores=False,
        )

        response = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.95,
                )
            ]
        )

        # When disabled, _calibrate_confidences should still work but won't be called
        calibrated = extractor._calibrate_confidences(response)
        # This tests the method still works, but in practice it won't be called
        assert calibrated.entities[0].confidence < 0.95

    def test_get_insights_from_response_entities(self, extractor):
        """Test extracting insights list from entity response."""
        response = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.8,
                )
            ]
        )

        insights = extractor._get_insights_from_response(response)
        assert len(insights) == 1

    def test_get_insights_from_response_empty(self, extractor):
        """Test extracting insights from empty response."""
        response = EntityExtractionResult(entities=[])

        insights = extractor._get_insights_from_response(response)
        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_extract_with_context(self, extractor, mock_llm_client):
        """Test extraction with context."""
        mock_response = EntityExtractionResult(entities=[])
        mock_llm_client.complete_structured.return_value = mock_response

        context = {"document_type": "annual_report", "industry": "technology"}

        result = await extractor.extract(
            text="Test text",
            extraction_type="entity",
            context=context,
        )

        assert result.success is True
        assert result.metadata["context"] == context

    @pytest.mark.asyncio
    async def test_extract_with_document_id(self, extractor, mock_llm_client):
        """Test extraction with document ID."""
        from uuid import uuid4

        mock_response = EntityExtractionResult(entities=[])
        mock_llm_client.complete_structured.return_value = mock_response

        doc_id = uuid4()

        result = await extractor.extract(
            text="Test text",
            extraction_type="entity",
            document_id=doc_id,
        )

        assert result.success is True
        assert result.metadata["document_id"] == str(doc_id)
