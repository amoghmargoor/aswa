from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TrendType(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"
    SEASONAL = "seasonal"
    EMERGING = "emerging"


class TrendStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class TrendCategory(str, Enum):
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    ENTITY = "entity"
    TOPIC = "topic"
    SENTIMENT = "sentiment"


class Trend(BaseModel):
    """A detected trend."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str
    description: str
    category: TrendCategory
    trend_type: TrendType
    strength: TrendStrength
    confidence: float = Field(ge=0, le=1)

    # Time series data
    start_date: datetime
    end_date: datetime
    data_points: list[dict] = Field(default_factory=list)

    # Statistics
    change_percentage: float = 0.0
    baseline_value: float = 0.0
    current_value: float = 0.0
    peak_value: float = 0.0

    # Related entities
    related_entities: list[str] = Field(default_factory=list)
    related_documents: list[UUID] = Field(default_factory=list)

    # Forecasting
    forecast: list[dict] | None = None
    forecast_confidence: float = 0.0

    detected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendAlert(BaseModel):
    """An alert for significant trend change."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    trend_id: UUID
    alert_type: str  # "new_trend", "trend_change", "threshold_exceeded"
    severity: str  # "low", "medium", "high"
    title: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: datetime | None = None


class TrendSummary(BaseModel):
    """Summary of trends for a tenant."""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    total_trends: int = 0
    increasing_trends: int = 0
    decreasing_trends: int = 0
    emerging_trends: int = 0
    top_trends: list[Trend] = Field(default_factory=list)
    alerts: list[TrendAlert] = Field(default_factory=list)
