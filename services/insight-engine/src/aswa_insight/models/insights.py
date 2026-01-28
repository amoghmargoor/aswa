"""Unified insight model for storage."""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .base import SourceReference
from .entities import ExtractedEntity
from .opportunities import ExtractedOpportunity, ImpactLevel
from .patterns import ExtractedPattern
from .risks import ExtractedRisk, Severity


class InsightType(str, Enum):
    """Types of insights."""

    ENTITY = "entity"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    PATTERN = "pattern"


class Insight(BaseModel):
    """Unified insight model for storage."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    document_id: UUID
    insight_type: InsightType
    title: str
    description: str
    confidence: float
    severity: Severity | None = None  # For risks
    impact: ImpactLevel | None = None  # For opportunities
    category: str | None = None
    raw_data: dict = Field(
        default_factory=dict, description="Original extracted data"
    )
    sources: list[SourceReference] = Field(default_factory=list)
    related_entity_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_validated: bool = False
    user_feedback: str | None = None

    @classmethod
    def from_entity(
        cls, entity: ExtractedEntity, tenant_id: UUID, document_id: UUID
    ) -> "Insight":
        """Create insight from extracted entity."""
        # Get enum value properly (it might already be a string due to use_enum_values)
        entity_type_val = entity.entity_type if isinstance(entity.entity_type, str) else entity.entity_type.value

        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.ENTITY,
            title=entity.name,
            description=entity.description,
            confidence=entity.confidence,
            category=entity_type_val,
            raw_data={
                "name": entity.name,
                "entity_type": entity_type_val,
                "aliases": entity.aliases,
                "attributes": entity.attributes,
            },
            sources=entity.sources,
        )

    @classmethod
    def from_risk(
        cls, risk: ExtractedRisk, tenant_id: UUID, document_id: UUID
    ) -> "Insight":
        """Create insight from extracted risk."""
        # Get enum values properly (they might already be strings due to use_enum_values)
        category_val = risk.category if isinstance(risk.category, str) else risk.category.value
        severity_val = risk.severity if isinstance(risk.severity, str) else risk.severity.value
        likelihood_val = risk.likelihood if isinstance(risk.likelihood, str) else risk.likelihood.value
        time_horizon_val = None
        if risk.time_horizon:
            time_horizon_val = risk.time_horizon if isinstance(risk.time_horizon, str) else risk.time_horizon.value

        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.RISK,
            title=risk.title,
            description=risk.description,
            confidence=risk.confidence,
            severity=risk.severity,
            category=category_val,
            raw_data={
                "severity": severity_val,
                "likelihood": likelihood_val,
                "time_horizon": time_horizon_val,
                "impact_description": risk.impact_description,
                "affected_areas": risk.affected_areas,
                "related_entities": risk.related_entities,
                "mitigations": [m.model_dump() for m in risk.mitigations],
                "risk_score": risk.risk_score,
            },
            sources=risk.sources,
        )

    @classmethod
    def from_opportunity(
        cls, opportunity: ExtractedOpportunity, tenant_id: UUID, document_id: UUID
    ) -> "Insight":
        """Create insight from extracted opportunity."""
        # Get enum values properly (they might already be strings due to use_enum_values)
        category_val = opportunity.category if isinstance(opportunity.category, str) else opportunity.category.value
        impact_val = opportunity.impact if isinstance(opportunity.impact, str) else opportunity.impact.value
        effort_val = opportunity.effort if isinstance(opportunity.effort, str) else opportunity.effort.value
        time_to_value_val = None
        if opportunity.time_to_value:
            time_to_value_val = opportunity.time_to_value if isinstance(opportunity.time_to_value, str) else opportunity.time_to_value.value

        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.OPPORTUNITY,
            title=opportunity.title,
            description=opportunity.description,
            confidence=opportunity.confidence,
            impact=opportunity.impact,
            category=category_val,
            raw_data={
                "impact": impact_val,
                "effort": effort_val,
                "time_to_value": time_to_value_val,
                "potential_value": opportunity.potential_value,
                "prerequisites": opportunity.prerequisites,
                "risks": opportunity.risks,
                "related_entities": opportunity.related_entities,
                "action_items": [a.model_dump() for a in opportunity.action_items],
                "strategic_alignment": opportunity.strategic_alignment,
            },
            sources=opportunity.sources,
        )

    @classmethod
    def from_pattern(
        cls, pattern: ExtractedPattern, tenant_id: UUID, document_id: UUID
    ) -> "Insight":
        """Create insight from extracted pattern."""
        # Get enum values properly (they might already be strings due to use_enum_values)
        pattern_type_val = pattern.pattern_type if isinstance(pattern.pattern_type, str) else pattern.pattern_type.value
        frequency_val = None
        if pattern.frequency:
            frequency_val = pattern.frequency if isinstance(pattern.frequency, str) else pattern.frequency.value
        trend_direction_val = None
        if pattern.trend_direction:
            trend_direction_val = pattern.trend_direction if isinstance(pattern.trend_direction, str) else pattern.trend_direction.value

        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.PATTERN,
            title=pattern.title,
            description=pattern.description,
            confidence=pattern.confidence,
            category=pattern_type_val,
            raw_data={
                "pattern_type": pattern_type_val,
                "frequency": frequency_val,
                "trend_direction": trend_direction_val,
                "magnitude": pattern.magnitude,
                "time_period": pattern.time_period,
                "data_points": [d.model_dump() for d in pattern.data_points],
                "related_entities": pattern.related_entities,
                "implications": pattern.implications,
                "statistical_significance": pattern.statistical_significance,
            },
            sources=pattern.sources,
        )
