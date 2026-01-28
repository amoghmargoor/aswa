"""Unified insight model for storage."""

from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_validated: bool = False
    user_feedback: str | None = None

    @classmethod
    def from_entity(
        cls, entity: ExtractedEntity, tenant_id: UUID, document_id: UUID
    ) -> "Insight":
        """Create insight from extracted entity."""
        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.ENTITY,
            title=entity.name,
            description=entity.description,
            confidence=entity.confidence,
            category=entity.entity_type.value,
            raw_data={
                "name": entity.name,
                "entity_type": entity.entity_type.value,
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
        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.RISK,
            title=risk.title,
            description=risk.description,
            confidence=risk.confidence,
            severity=risk.severity,
            category=risk.category.value,
            raw_data={
                "severity": risk.severity.value,
                "likelihood": risk.likelihood.value,
                "time_horizon": risk.time_horizon.value if risk.time_horizon else None,
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
        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.OPPORTUNITY,
            title=opportunity.title,
            description=opportunity.description,
            confidence=opportunity.confidence,
            impact=opportunity.impact,
            category=opportunity.category.value,
            raw_data={
                "impact": opportunity.impact.value,
                "effort": opportunity.effort.value,
                "time_to_value": (
                    opportunity.time_to_value.value if opportunity.time_to_value else None
                ),
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
        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            insight_type=InsightType.PATTERN,
            title=pattern.title,
            description=pattern.description,
            confidence=pattern.confidence,
            category=pattern.pattern_type.value,
            raw_data={
                "pattern_type": pattern.pattern_type.value,
                "frequency": pattern.frequency.value if pattern.frequency else None,
                "trend_direction": (
                    pattern.trend_direction.value if pattern.trend_direction else None
                ),
                "magnitude": pattern.magnitude,
                "time_period": pattern.time_period,
                "data_points": [d.model_dump() for d in pattern.data_points],
                "related_entities": pattern.related_entities,
                "implications": pattern.implications,
                "statistical_significance": pattern.statistical_significance,
            },
            sources=pattern.sources,
        )
