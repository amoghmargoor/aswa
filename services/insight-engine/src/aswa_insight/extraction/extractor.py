import time
from dataclasses import dataclass, field
from typing import Any, TypeVar
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from aswa_insight.llm.client import LLMClient
from aswa_insight.prompts.base import prompt_manager
from aswa_insight.scoring.confidence import ConfidenceScorer, calibrate_confidence
from aswa_insight.scoring.quality import ExtractionQuality, QualityScorer

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


@dataclass
class ExtractionResult:
    """Result of a structured extraction."""

    id: UUID = field(default_factory=uuid4)
    success: bool = True
    extraction_type: str = ""
    result: BaseModel | None = None
    raw_response: dict | None = None
    error: str | None = None
    processing_time_ms: int = 0
    token_count: int = 0
    quality: ExtractionQuality | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "success": self.success,
            "extraction_type": self.extraction_type,
            "result": self.result.model_dump() if self.result else None,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms,
            "token_count": self.token_count,
        }


class StructuredExtractor:
    """Execute structured extractions using LLM and instructor."""

    def __init__(
        self,
        llm_client: LLMClient,
        confidence_scorer: ConfidenceScorer | None = None,
        quality_scorer: QualityScorer | None = None,
        max_retries: int = 3,
        calibrate_confidence_scores: bool = True,
    ):
        self.llm_client = llm_client
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.quality_scorer = quality_scorer or QualityScorer()
        self.max_retries = max_retries
        self.calibrate_confidence_scores = calibrate_confidence_scores

        # Metrics
        self._extraction_count = 0
        self._error_count = 0
        self._total_tokens = 0

    async def extract(
        self,
        text: str,
        extraction_type: str,
        context: dict[str, Any] | None = None,
        document_id: UUID | None = None,
    ) -> ExtractionResult:
        """Perform structured extraction.

        Args:
            text: Text to extract from
            extraction_type: Type of extraction (entity, risk, opportunity, pattern, combined)
            context: Optional context for the extraction
            document_id: Optional document ID

        Returns:
            ExtractionResult with extracted data or error
        """
        start_time = time.monotonic()
        result_id = uuid4()

        logger.info(
            "Starting extraction",
            extraction_id=str(result_id),
            extraction_type=extraction_type,
            text_length=len(text),
        )

        try:
            # Get prompt template
            template = prompt_manager.get(f"{extraction_type}_extraction")

            # Build messages
            messages = template.get_messages(text, context)

            # Count tokens (approximate)
            token_count = await self.llm_client.count_tokens(text)

            # Perform structured extraction
            response = await self.llm_client.complete_structured(
                messages=messages,
                response_model=template.response_model,
                max_tokens=template.max_tokens,
                temperature=template.temperature,
                max_retries=self.max_retries,
            )

            # Post-process: calibrate confidence scores
            if self.calibrate_confidence_scores:
                response = self._calibrate_confidences(response)

            # Calculate quality
            processing_time_ms = int((time.monotonic() - start_time) * 1000)
            quality = self._assess_quality(
                document_id=str(document_id) if document_id else str(result_id),
                extraction_type=extraction_type,
                response=response,
                processing_time_ms=processing_time_ms,
            )

            self._extraction_count += 1
            self._total_tokens += token_count

            logger.info(
                "Extraction completed",
                extraction_id=str(result_id),
                extraction_type=extraction_type,
                processing_time_ms=processing_time_ms,
                quality_score=quality.quality_score if quality else None,
            )

            return ExtractionResult(
                id=result_id,
                success=True,
                extraction_type=extraction_type,
                result=response,
                processing_time_ms=processing_time_ms,
                token_count=token_count,
                quality=quality,
                metadata={
                    "document_id": str(document_id) if document_id else None,
                    "context": context,
                },
            )

        except ValueError as e:
            # Template not found or validation error
            self._error_count += 1
            logger.error(
                "Extraction failed - validation error",
                extraction_id=str(result_id),
                error=str(e),
            )
            return ExtractionResult(
                id=result_id,
                success=False,
                extraction_type=extraction_type,
                error=f"Validation error: {str(e)}",
                processing_time_ms=int((time.monotonic() - start_time) * 1000),
            )

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Extraction failed",
                extraction_id=str(result_id),
                extraction_type=extraction_type,
                error=str(e),
            )
            return ExtractionResult(
                id=result_id,
                success=False,
                extraction_type=extraction_type,
                error=str(e),
                processing_time_ms=int((time.monotonic() - start_time) * 1000),
            )

    async def extract_all(
        self,
        text: str,
        extraction_types: list[str] | None = None,
        context: dict[str, Any] | None = None,
        document_id: UUID | None = None,
    ) -> dict[str, ExtractionResult]:
        """Perform multiple extraction types.

        Args:
            text: Text to extract from
            extraction_types: List of extraction types (default: all)
            context: Optional context
            document_id: Optional document ID

        Returns:
            Dict mapping extraction type to result
        """
        if extraction_types is None:
            extraction_types = ["entity", "risk", "opportunity", "pattern"]

        results = {}
        for ext_type in extraction_types:
            results[ext_type] = await self.extract(
                text=text,
                extraction_type=ext_type,
                context=context,
                document_id=document_id,
            )

        return results

    def _calibrate_confidences(self, response: BaseModel) -> BaseModel:
        """Calibrate confidence scores in response."""
        # Get model data
        data = response.model_dump()

        # Find and calibrate confidence fields
        self._calibrate_recursive(data)

        # Reconstruct model
        return response.model_validate(data)

    def _calibrate_recursive(self, obj: Any) -> None:
        """Recursively calibrate confidence values."""
        if isinstance(obj, dict):
            if "confidence" in obj and isinstance(obj["confidence"], (int, float)):
                obj["confidence"] = calibrate_confidence(obj["confidence"])
            for value in obj.values():
                self._calibrate_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                self._calibrate_recursive(item)

    def _assess_quality(
        self,
        document_id: str,
        extraction_type: str,
        response: BaseModel,
        processing_time_ms: int,
    ) -> ExtractionQuality:
        """Assess extraction quality."""
        # Extract insights based on response type
        insights = self._get_insights_from_response(response)

        return self.quality_scorer.assess_extraction(
            document_id=document_id,
            extraction_type=extraction_type,
            insights=insights,
            processing_time_ms=processing_time_ms,
        )

    def _get_insights_from_response(self, response: BaseModel) -> list:
        """Extract insight list from response model."""
        # Look for common list fields on the model directly
        for field_name in ["entities", "risks", "opportunities", "patterns"]:
            if hasattr(response, field_name):
                items = getattr(response, field_name)
                if isinstance(items, list):
                    return items

        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get extractor metrics."""
        return {
            "extraction_count": self._extraction_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
            "error_rate": self._error_count / max(1, self._extraction_count),
        }
