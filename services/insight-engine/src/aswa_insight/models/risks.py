"""Risk extraction models."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ExtractedInsightBase


class RiskCategory(str, Enum):
    """Categories of business risks."""

    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    STRATEGIC = "strategic"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    REPUTATIONAL = "reputational"
    MARKET = "market"
    TECHNOLOGY = "technology"
    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"


class Severity(str, Enum):
    """Risk severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class Likelihood(str, Enum):
    """Risk likelihood levels."""

    ALMOST_CERTAIN = "almost_certain"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    RARE = "rare"


class TimeHorizon(str, Enum):
    """Time horizon for risk materialization."""

    IMMEDIATE = "immediate"  # < 1 month
    SHORT_TERM = "short_term"  # 1-6 months
    MEDIUM_TERM = "medium_term"  # 6-18 months
    LONG_TERM = "long_term"  # > 18 months


class MitigationStrategy(BaseModel):
    """A suggested mitigation for a risk."""

    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    effort: Literal["low", "medium", "high"]
    effectiveness: Literal["low", "medium", "high"]


class ExtractedRisk(ExtractedInsightBase):
    """A risk identified in the document."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    category: RiskCategory
    severity: Severity
    likelihood: Likelihood
    time_horizon: TimeHorizon | None = None
    impact_description: str = Field(
        ..., max_length=1000, description="Potential impact"
    )
    affected_areas: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    mitigations: list[MitigationStrategy] = Field(default_factory=list)
    risk_score: Annotated[float, Field(ge=0.0, le=100.0)] | None = None


class RiskExtractionResult(BaseModel):
    """Result of risk extraction from a document."""

    risks: list[ExtractedRisk] = Field(default_factory=list)
    overall_risk_level: Severity | None = None
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
