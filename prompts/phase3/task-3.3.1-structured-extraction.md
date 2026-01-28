# Task 3.3.1: Instructor-based Structured Extraction

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The following components are already implemented:
- LLM clients at `/services/insight-engine/src/aswa_insight/llm/` with `complete_structured()` method
- Extraction models at `/services/insight-engine/src/aswa_insight/models/`
- Prompt templates at `/services/insight-engine/src/aswa_insight/prompts/`
- Confidence scoring at `/services/insight-engine/src/aswa_insight/scoring/`

## Objective

Create the core extraction service that uses the instructor library for structured LLM output extraction. This service should:
1. Execute structured extractions using prompt templates
2. Validate and process extraction results
3. Handle errors and retries gracefully
4. Track extraction metrics

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/extraction/__init__.py`
```python
from .extractor import StructuredExtractor, ExtractionResult
from .validators import ExtractionValidator, ValidationResult
from .processor import ExtractionProcessor

__all__ = [
    "StructuredExtractor",
    "ExtractionResult",
    "ExtractionValidator",
    "ValidationResult",
    "ExtractionProcessor",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/extraction/extractor.py`
Core extraction engine using instructor:

```python
import time
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from aswa_insight.llm.client import LLMClient
from aswa_insight.prompts.base import PromptTemplate, prompt_manager
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
        data = response.model_dump()

        # Look for common list fields
        for field in ["entities", "risks", "opportunities", "patterns"]:
            if field in data and isinstance(data[field], list):
                return data[field]

        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get extractor metrics."""
        return {
            "extraction_count": self._extraction_count,
            "error_count": self._error_count,
            "total_tokens": self._total_tokens,
            "error_rate": self._error_count / max(1, self._extraction_count),
        }
```

### 3. Create `/services/insight-engine/src/aswa_insight/extraction/validators.py`
Validation layer for extractions:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import structlog
from pydantic import BaseModel, ValidationError

from aswa_insight.models.base import ExtractedInsightBase

logger = structlog.get_logger()


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A validation issue found."""
    field: str
    message: str
    severity: ValidationSeverity
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    cleaned_data: BaseModel | None = None

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)


class ExtractionValidator:
    """Validate extraction results."""

    def __init__(
        self,
        min_confidence: float = 0.0,
        max_insights_per_extraction: int = 100,
        require_sources: bool = False,
    ):
        self.min_confidence = min_confidence
        self.max_insights_per_extraction = max_insights_per_extraction
        self.require_sources = require_sources
        self._custom_validators: list[Callable[[BaseModel], list[ValidationIssue]]] = []

    def register_validator(
        self,
        validator: Callable[[BaseModel], list[ValidationIssue]],
    ) -> None:
        """Register a custom validator function."""
        self._custom_validators.append(validator)

    def validate(self, extraction: BaseModel) -> ValidationResult:
        """Validate an extraction result.

        Args:
            extraction: The extracted data to validate

        Returns:
            ValidationResult with issues and cleaned data
        """
        issues: list[ValidationIssue] = []

        # Get data as dict for validation
        data = extraction.model_dump()

        # Validate confidence scores
        issues.extend(self._validate_confidences(data))

        # Validate insight counts
        issues.extend(self._validate_counts(data))

        # Validate sources if required
        if self.require_sources:
            issues.extend(self._validate_sources(data))

        # Run custom validators
        for validator in self._custom_validators:
            try:
                issues.extend(validator(extraction))
            except Exception as e:
                logger.warning("Custom validator failed", error=str(e))

        # Check for duplicate insights
        issues.extend(self._check_duplicates(data))

        # Determine if valid (no errors)
        valid = all(i.severity != ValidationSeverity.ERROR for i in issues)

        # Create cleaned data if valid
        cleaned = None
        if valid:
            cleaned = self._clean_data(extraction, issues)

        return ValidationResult(
            valid=valid,
            issues=issues,
            cleaned_data=cleaned,
        )

    def _validate_confidences(self, data: dict) -> list[ValidationIssue]:
        """Validate confidence scores."""
        issues = []

        def check_confidence(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                if "confidence" in obj:
                    conf = obj["confidence"]
                    if conf < self.min_confidence:
                        issues.append(ValidationIssue(
                            field=f"{path}.confidence",
                            message=f"Confidence {conf:.2f} below minimum {self.min_confidence:.2f}",
                            severity=ValidationSeverity.WARNING,
                            value=conf,
                        ))
                    if not 0 <= conf <= 1:
                        issues.append(ValidationIssue(
                            field=f"{path}.confidence",
                            message=f"Confidence {conf} out of range [0, 1]",
                            severity=ValidationSeverity.ERROR,
                            value=conf,
                        ))
                for key, value in obj.items():
                    check_confidence(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_confidence(item, f"{path}[{i}]")

        check_confidence(data)
        return issues

    def _validate_counts(self, data: dict) -> list[ValidationIssue]:
        """Validate insight counts."""
        issues = []

        for field in ["entities", "risks", "opportunities", "patterns"]:
            if field in data and isinstance(data[field], list):
                count = len(data[field])
                if count > self.max_insights_per_extraction:
                    issues.append(ValidationIssue(
                        field=field,
                        message=f"Too many {field}: {count} > {self.max_insights_per_extraction}",
                        severity=ValidationSeverity.WARNING,
                        value=count,
                    ))

        return issues

    def _validate_sources(self, data: dict) -> list[ValidationIssue]:
        """Validate source references."""
        issues = []

        def check_sources(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                if "sources" in obj:
                    sources = obj["sources"]
                    if not sources or len(sources) == 0:
                        issues.append(ValidationIssue(
                            field=f"{path}.sources",
                            message="Missing source references",
                            severity=ValidationSeverity.WARNING,
                        ))
                for key, value in obj.items():
                    check_sources(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_sources(item, f"{path}[{i}]")

        check_sources(data)
        return issues

    def _check_duplicates(self, data: dict) -> list[ValidationIssue]:
        """Check for duplicate insights."""
        issues = []

        for field in ["entities", "risks", "opportunities", "patterns"]:
            if field in data and isinstance(data[field], list):
                items = data[field]
                seen_titles = set()

                for i, item in enumerate(items):
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("name", "")
                        if title in seen_titles:
                            issues.append(ValidationIssue(
                                field=f"{field}[{i}]",
                                message=f"Duplicate {field[:-1]}: {title}",
                                severity=ValidationSeverity.WARNING,
                                value=title,
                            ))
                        seen_titles.add(title)

        return issues

    def _clean_data(
        self,
        extraction: BaseModel,
        issues: list[ValidationIssue],
    ) -> BaseModel:
        """Clean extraction data based on validation issues."""
        data = extraction.model_dump()

        # Filter out low-confidence items if any
        for field in ["entities", "risks", "opportunities", "patterns"]:
            if field in data and isinstance(data[field], list):
                data[field] = [
                    item for item in data[field]
                    if item.get("confidence", 1.0) >= self.min_confidence
                ]

        return extraction.model_validate(data)
```

### 4. Create `/services/insight-engine/src/aswa_insight/extraction/processor.py`
High-level extraction processor:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from aswa_insight.extraction.extractor import StructuredExtractor, ExtractionResult
from aswa_insight.extraction.validators import ExtractionValidator, ValidationResult
from aswa_insight.models.insights import Insight, InsightType
from aswa_insight.scoring.quality import QualityScorer, DocumentQuality

logger = structlog.get_logger()


@dataclass
class ProcessingResult:
    """Result of document processing."""
    document_id: UUID
    tenant_id: UUID
    extraction_results: dict[str, ExtractionResult]
    validation_results: dict[str, ValidationResult]
    insights: list[Insight]
    document_quality: DocumentQuality | None = None
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and all(
            r.success for r in self.extraction_results.values()
        )

    @property
    def insight_count(self) -> int:
        return len(self.insights)


class ExtractionProcessor:
    """High-level processor for document extraction."""

    def __init__(
        self,
        extractor: StructuredExtractor,
        validator: ExtractionValidator | None = None,
        quality_scorer: QualityScorer | None = None,
        extraction_types: list[str] | None = None,
    ):
        self.extractor = extractor
        self.validator = validator or ExtractionValidator()
        self.quality_scorer = quality_scorer or QualityScorer()
        self.extraction_types = extraction_types or [
            "entity", "risk", "opportunity", "pattern"
        ]

    async def process_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        text: str,
        context: dict[str, Any] | None = None,
        extraction_types: list[str] | None = None,
    ) -> ProcessingResult:
        """Process a document and extract all insights.

        Args:
            document_id: Document identifier
            tenant_id: Tenant identifier
            text: Document text content
            context: Optional extraction context
            extraction_types: Types to extract (default: all)

        Returns:
            ProcessingResult with all extractions and insights
        """
        types_to_extract = extraction_types or self.extraction_types

        logger.info(
            "Processing document",
            document_id=str(document_id),
            tenant_id=str(tenant_id),
            text_length=len(text),
            extraction_types=types_to_extract,
        )

        # Assess document quality
        doc_quality = self.quality_scorer.assess_document(
            document_id=str(document_id),
            text=text,
        )

        # Perform extractions
        extraction_results = await self.extractor.extract_all(
            text=text,
            extraction_types=types_to_extract,
            context=context,
            document_id=document_id,
        )

        # Validate extractions
        validation_results = {}
        for ext_type, ext_result in extraction_results.items():
            if ext_result.success and ext_result.result:
                validation_results[ext_type] = self.validator.validate(ext_result.result)
            else:
                validation_results[ext_type] = ValidationResult(valid=False, issues=[])

        # Convert to unified insights
        insights = self._create_insights(
            extraction_results=extraction_results,
            validation_results=validation_results,
            document_id=document_id,
            tenant_id=tenant_id,
        )

        # Collect errors
        errors = [
            f"{ext_type}: {r.error}"
            for ext_type, r in extraction_results.items()
            if not r.success and r.error
        ]

        logger.info(
            "Document processing complete",
            document_id=str(document_id),
            insight_count=len(insights),
            error_count=len(errors),
        )

        return ProcessingResult(
            document_id=document_id,
            tenant_id=tenant_id,
            extraction_results=extraction_results,
            validation_results=validation_results,
            insights=insights,
            document_quality=doc_quality,
            errors=errors,
        )

    def _create_insights(
        self,
        extraction_results: dict[str, ExtractionResult],
        validation_results: dict[str, ValidationResult],
        document_id: UUID,
        tenant_id: UUID,
    ) -> list[Insight]:
        """Create unified insights from extraction results."""
        insights = []

        for ext_type, ext_result in extraction_results.items():
            if not ext_result.success or not ext_result.result:
                continue

            validation = validation_results.get(ext_type)
            if validation and not validation.valid:
                continue

            # Use cleaned data if available
            data = validation.cleaned_data if validation and validation.cleaned_data else ext_result.result

            # Convert based on extraction type
            if ext_type == "entity":
                insights.extend(self._entities_to_insights(data, tenant_id, document_id))
            elif ext_type == "risk":
                insights.extend(self._risks_to_insights(data, tenant_id, document_id))
            elif ext_type == "opportunity":
                insights.extend(self._opportunities_to_insights(data, tenant_id, document_id))
            elif ext_type == "pattern":
                insights.extend(self._patterns_to_insights(data, tenant_id, document_id))

        return insights

    def _entities_to_insights(
        self,
        data: Any,
        tenant_id: UUID,
        document_id: UUID,
    ) -> list[Insight]:
        """Convert entities to insights."""
        insights = []
        entities = getattr(data, "entities", []) if hasattr(data, "entities") else []

        for entity in entities:
            insight = Insight(
                tenant_id=tenant_id,
                document_id=document_id,
                insight_type=InsightType.ENTITY,
                title=entity.name if hasattr(entity, "name") else str(entity.get("name", "")),
                description=entity.description if hasattr(entity, "description") else str(entity.get("description", "")),
                confidence=entity.confidence if hasattr(entity, "confidence") else entity.get("confidence", 0.5),
                category=entity.entity_type.value if hasattr(entity, "entity_type") else entity.get("entity_type", "other"),
                raw_data=entity.model_dump() if hasattr(entity, "model_dump") else entity,
            )
            insights.append(insight)

        return insights

    def _risks_to_insights(
        self,
        data: Any,
        tenant_id: UUID,
        document_id: UUID,
    ) -> list[Insight]:
        """Convert risks to insights."""
        insights = []
        risks = getattr(data, "risks", []) if hasattr(data, "risks") else []

        for risk in risks:
            insight = Insight(
                tenant_id=tenant_id,
                document_id=document_id,
                insight_type=InsightType.RISK,
                title=risk.title if hasattr(risk, "title") else risk.get("title", ""),
                description=risk.description if hasattr(risk, "description") else risk.get("description", ""),
                confidence=risk.confidence if hasattr(risk, "confidence") else risk.get("confidence", 0.5),
                severity=risk.severity if hasattr(risk, "severity") else risk.get("severity"),
                category=risk.category.value if hasattr(risk, "category") else risk.get("category", "other"),
                raw_data=risk.model_dump() if hasattr(risk, "model_dump") else risk,
            )
            insights.append(insight)

        return insights

    def _opportunities_to_insights(
        self,
        data: Any,
        tenant_id: UUID,
        document_id: UUID,
    ) -> list[Insight]:
        """Convert opportunities to insights."""
        insights = []
        opportunities = getattr(data, "opportunities", []) if hasattr(data, "opportunities") else []

        for opp in opportunities:
            insight = Insight(
                tenant_id=tenant_id,
                document_id=document_id,
                insight_type=InsightType.OPPORTUNITY,
                title=opp.title if hasattr(opp, "title") else opp.get("title", ""),
                description=opp.description if hasattr(opp, "description") else opp.get("description", ""),
                confidence=opp.confidence if hasattr(opp, "confidence") else opp.get("confidence", 0.5),
                impact=opp.impact if hasattr(opp, "impact") else opp.get("impact"),
                category=opp.category.value if hasattr(opp, "category") else opp.get("category", "other"),
                raw_data=opp.model_dump() if hasattr(opp, "model_dump") else opp,
            )
            insights.append(insight)

        return insights

    def _patterns_to_insights(
        self,
        data: Any,
        tenant_id: UUID,
        document_id: UUID,
    ) -> list[Insight]:
        """Convert patterns to insights."""
        insights = []
        patterns = getattr(data, "patterns", []) if hasattr(data, "patterns") else []

        for pattern in patterns:
            insight = Insight(
                tenant_id=tenant_id,
                document_id=document_id,
                insight_type=InsightType.PATTERN,
                title=pattern.title if hasattr(pattern, "title") else pattern.get("title", ""),
                description=pattern.description if hasattr(pattern, "description") else pattern.get("description", ""),
                confidence=pattern.confidence if hasattr(pattern, "confidence") else pattern.get("confidence", 0.5),
                category=pattern.pattern_type.value if hasattr(pattern, "pattern_type") else pattern.get("pattern_type", "other"),
                raw_data=pattern.model_dump() if hasattr(pattern, "model_dump") else pattern,
            )
            insights.append(insight)

        return insights
```

## Test Requirements

### Create `/services/insight-engine/tests/extraction/__init__.py`

### Create `/services/insight-engine/tests/extraction/test_extractor.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_insight.extraction.extractor import StructuredExtractor, ExtractionResult
from aswa_insight.models.entities import EntityExtractionResult, ExtractedEntity, EntityType


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

    def test_to_dict_with_result(self):
        """Test result with model serialization."""


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
        mock_llm_client.complete_structured.return_value = MagicMock()

        results = await extractor.extract_all(
            text="Test text",
            extraction_types=["entity", "risk"],
        )

        assert "entity" in results
        assert "risk" in results

    def test_get_metrics(self, extractor):
        """Test metrics retrieval."""
        metrics = extractor.get_metrics()
        assert "extraction_count" in metrics
        assert "error_count" in metrics

    def test_calibrate_confidences(self, extractor):
        """Test confidence calibration."""
        # High confidence should be reduced
```

### Create `/services/insight-engine/tests/extraction/test_validators.py`
```python
import pytest
from aswa_insight.extraction.validators import (
    ExtractionValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
)
from aswa_insight.models.entities import EntityExtractionResult, ExtractedEntity, EntityType


class TestExtractionValidator:
    @pytest.fixture
    def validator(self):
        return ExtractionValidator(min_confidence=0.5)

    def test_validate_valid_extraction(self, validator):
        """Test validation of valid extraction."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test description",
                    confidence=0.8,
                )
            ]
        )

        result = validator.validate(extraction)
        assert result.valid is True

    def test_validate_low_confidence(self, validator):
        """Test validation flags low confidence."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Test",
                    entity_type=EntityType.ORGANIZATION,
                    description="Test",
                    confidence=0.3,  # Below threshold
                )
            ]
        )

        result = validator.validate(extraction)
        assert any(i.severity == ValidationSeverity.WARNING for i in result.issues)

    def test_validate_out_of_range_confidence(self, validator):
        """Test validation errors on out-of-range confidence."""
        # This should be caught by Pydantic, but test the validator too

    def test_validate_too_many_insights(self):
        """Test validation warns on too many insights."""
        validator = ExtractionValidator(max_insights_per_extraction=5)

        entities = [
            ExtractedEntity(
                name=f"Entity {i}",
                entity_type=EntityType.OTHER,
                description="Test",
                confidence=0.8,
            )
            for i in range(10)
        ]
        extraction = EntityExtractionResult(entities=entities)

        result = validator.validate(extraction)
        assert any("Too many" in i.message for i in result.issues)

    def test_validate_duplicates(self, validator):
        """Test validation detects duplicates."""
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(name="Same Name", entity_type=EntityType.ORGANIZATION, description="First", confidence=0.8),
                ExtractedEntity(name="Same Name", entity_type=EntityType.ORGANIZATION, description="Second", confidence=0.7),
            ]
        )

        result = validator.validate(extraction)
        assert any("Duplicate" in i.message for i in result.issues)

    def test_custom_validator(self, validator):
        """Test custom validator registration."""
        def custom_check(extraction):
            return [ValidationIssue(
                field="custom",
                message="Custom check",
                severity=ValidationSeverity.INFO,
            )]

        validator.register_validator(custom_check)
        extraction = EntityExtractionResult(entities=[])

        result = validator.validate(extraction)
        assert any(i.field == "custom" for i in result.issues)


class TestValidationResult:
    def test_error_count(self):
        """Test error count calculation."""
        result = ValidationResult(
            valid=False,
            issues=[
                ValidationIssue("f1", "msg1", ValidationSeverity.ERROR),
                ValidationIssue("f2", "msg2", ValidationSeverity.WARNING),
                ValidationIssue("f3", "msg3", ValidationSeverity.ERROR),
            ]
        )
        assert result.error_count == 2
        assert result.warning_count == 1
```

### Create `/services/insight-engine/tests/extraction/test_processor.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.extraction.processor import ExtractionProcessor, ProcessingResult
from aswa_insight.extraction.extractor import StructuredExtractor, ExtractionResult
from aswa_insight.extraction.validators import ExtractionValidator
from aswa_insight.models.entities import EntityExtractionResult, ExtractedEntity, EntityType


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
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/extraction/ -v`
2. Verify imports: `python -c "from aswa_insight.extraction import *"`
3. Test integration with mock LLM client
