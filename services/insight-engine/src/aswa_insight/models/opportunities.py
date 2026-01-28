"""Opportunity extraction models."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ExtractedInsightBase
from .risks import TimeHorizon


class OpportunityCategory(str, Enum):
    """Categories of business opportunities."""

    GROWTH = "growth"
    COST_REDUCTION = "cost_reduction"
    EFFICIENCY = "efficiency"
    INNOVATION = "innovation"
    MARKET_EXPANSION = "market_expansion"
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    PRODUCT = "product"
    TALENT = "talent"
    TECHNOLOGY = "technology"
    OTHER = "other"


class ImpactLevel(str, Enum):
    """Potential impact levels."""

    TRANSFORMATIONAL = "transformational"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EffortLevel(str, Enum):
    """Required effort levels."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ActionItem(BaseModel):
    """A concrete action to pursue an opportunity."""

    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    priority: Literal["high", "medium", "low"]
    estimated_effort: EffortLevel
    dependencies: list[str] = Field(default_factory=list)


class ExtractedOpportunity(ExtractedInsightBase):
    """An opportunity identified in the document."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    category: OpportunityCategory
    impact: ImpactLevel
    effort: EffortLevel
    time_to_value: TimeHorizon | None = None
    potential_value: str | None = Field(
        None, description="Estimated value if quantifiable"
    )
    prerequisites: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list, description="Associated risks")
    related_entities: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    strategic_alignment: str | None = Field(None, max_length=500)


class OpportunityExtractionResult(BaseModel):
    """Result of opportunity extraction from a document."""

    opportunities: list[ExtractedOpportunity] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
