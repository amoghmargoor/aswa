from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    VOLUME_SPIKE = "volume_spike"
    VOLUME_DROP = "volume_drop"
    CONFIDENCE_ANOMALY = "confidence_anomaly"
    NEW_CATEGORY = "new_category"
    UNUSUAL_PATTERN = "unusual_pattern"
    OUTLIER_VALUE = "outlier_value"
    PROCESSING_ERROR = "processing_error"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Anomaly(BaseModel):
    """A detected anomaly."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    title: str
    description: str

    # Detection details
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    detection_method: str = ""
    confidence: float = Field(ge=0, le=1, default=0.8)

    # Statistical context
    expected_value: float | None = None
    actual_value: float | None = None
    deviation: float | None = None
    z_score: float | None = None

    # Related context
    related_documents: list[UUID] = Field(default_factory=list)
    related_insights: list[UUID] = Field(default_factory=list)
    affected_period_start: datetime | None = None
    affected_period_end: datetime | None = None

    # Resolution
    resolved: bool = False
    resolved_at: datetime | None = None
    resolution_notes: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class AnomalyStats(BaseModel):
    """Statistics for anomaly detection."""
    metric_name: str
    mean: float = 0.0
    std_dev: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    sample_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def update(self, value: float) -> None:
        """Update running statistics."""
        if self.sample_count == 0:
            self.mean = value
            self.min_value = value
            self.max_value = value
            self.std_dev = 0
        else:
            # Welford's algorithm for running mean and variance
            self.sample_count += 1
            delta = value - self.mean
            self.mean += delta / self.sample_count
            self.min_value = min(self.min_value, value)
            self.max_value = max(self.max_value, value)

        self.last_updated = datetime.utcnow()


class AnomalySummary(BaseModel):
    """Summary of anomalies for a period."""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    total_anomalies: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0
    anomalies: list[Anomaly] = Field(default_factory=list)
