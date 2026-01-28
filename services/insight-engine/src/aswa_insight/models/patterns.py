"""Pattern extraction models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ExtractedInsightBase


class PatternType(str, Enum):
    """Types of patterns that can be identified."""

    TREND = "trend"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    CYCLE = "cycle"
    THRESHOLD = "threshold"
    COMPARISON = "comparison"
    DISTRIBUTION = "distribution"
    SEQUENCE = "sequence"
    OTHER = "other"


class TrendDirection(str, Enum):
    """Direction of a trend."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"
    CYCLICAL = "cyclical"


class PatternFrequency(str, Enum):
    """Frequency of recurring patterns."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    IRREGULAR = "irregular"
    ONE_TIME = "one_time"


class DataPoint(BaseModel):
    """A data point in a pattern."""

    label: str
    value: float | str
    timestamp: datetime | None = None


class ExtractedPattern(ExtractedInsightBase):
    """A pattern identified in the document."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., max_length=3000)
    pattern_type: PatternType
    frequency: PatternFrequency | None = None
    trend_direction: TrendDirection | None = None
    magnitude: str | None = Field(None, description="Quantified magnitude if available")
    time_period: str | None = Field(None, description="Time period covered")
    data_points: list[DataPoint] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    statistical_significance: str | None = None


class PatternExtractionResult(BaseModel):
    """Result of pattern extraction from a document."""

    patterns: list[ExtractedPattern] = Field(default_factory=list)
    document_id: UUID | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
