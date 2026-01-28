from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog

from aswa_insight.extraction.extractor import ExtractionResult, StructuredExtractor
from aswa_insight.extraction.validators import ExtractionValidator, ValidationResult
from aswa_insight.models.insights import Insight, InsightType
from aswa_insight.scoring.quality import DocumentQuality, QualityScorer

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
    errors: list[str] = field(default_factory=list)

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
            "entity",
            "risk",
            "opportunity",
            "pattern",
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
            data = (
                validation.cleaned_data
                if validation and validation.cleaned_data
                else ext_result.result
            )

            # Convert based on extraction type
            if ext_type == "entity":
                insights.extend(self._entities_to_insights(data, tenant_id, document_id))
            elif ext_type == "risk":
                insights.extend(self._risks_to_insights(data, tenant_id, document_id))
            elif ext_type == "opportunity":
                insights.extend(
                    self._opportunities_to_insights(data, tenant_id, document_id)
                )
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
                description=entity.description
                if hasattr(entity, "description")
                else str(entity.get("description", "")),
                confidence=entity.confidence
                if hasattr(entity, "confidence")
                else entity.get("confidence", 0.5),
                category=entity.entity_type.value
                if hasattr(entity, "entity_type") and hasattr(entity.entity_type, "value")
                else (entity.entity_type if hasattr(entity, "entity_type") else entity.get("entity_type", "other")),
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
                description=risk.description
                if hasattr(risk, "description")
                else risk.get("description", ""),
                confidence=risk.confidence
                if hasattr(risk, "confidence")
                else risk.get("confidence", 0.5),
                severity=risk.severity if hasattr(risk, "severity") else risk.get("severity"),
                category=risk.category.value
                if hasattr(risk, "category") and hasattr(risk.category, "value")
                else (risk.category if hasattr(risk, "category") else risk.get("category", "other")),
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
        opportunities = (
            getattr(data, "opportunities", []) if hasattr(data, "opportunities") else []
        )

        for opp in opportunities:
            insight = Insight(
                tenant_id=tenant_id,
                document_id=document_id,
                insight_type=InsightType.OPPORTUNITY,
                title=opp.title if hasattr(opp, "title") else opp.get("title", ""),
                description=opp.description
                if hasattr(opp, "description")
                else opp.get("description", ""),
                confidence=opp.confidence
                if hasattr(opp, "confidence")
                else opp.get("confidence", 0.5),
                impact=opp.impact if hasattr(opp, "impact") else opp.get("impact"),
                category=opp.category.value
                if hasattr(opp, "category") and hasattr(opp.category, "value")
                else (opp.category if hasattr(opp, "category") else opp.get("category", "other")),
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
                description=pattern.description
                if hasattr(pattern, "description")
                else pattern.get("description", ""),
                confidence=pattern.confidence
                if hasattr(pattern, "confidence")
                else pattern.get("confidence", 0.5),
                category=pattern.pattern_type.value
                if hasattr(pattern, "pattern_type") and hasattr(pattern.pattern_type, "value")
                else (pattern.pattern_type if hasattr(pattern, "pattern_type") else pattern.get("pattern_type", "other")),
                raw_data=pattern.model_dump() if hasattr(pattern, "model_dump") else pattern,
            )
            insights.append(insight)

        return insights
