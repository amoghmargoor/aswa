# Task 4.3.3: Anomaly Detection

## Context

You are working on the ASWA query-service at `/services/query-service/`. Trend detection is complete. Now we need to detect anomalies in insights and document patterns.

## Objective

Create an anomaly detection service that:
1. Detects unusual patterns in insight extraction
2. Identifies document processing anomalies
3. Flags statistical outliers
4. Provides real-time anomaly alerts
5. Learns normal patterns over time

## Requirements

### 1. Create `/services/query-service/src/aswa_query/anomaly/__init__.py`
```python
from .detector import AnomalyDetector
from .models import Anomaly, AnomalyType, AnomalySeverity
from .algorithms import ZScoreDetector, IQRDetector, MovingAverageDetector
from .alerts import AnomalyAlertService

__all__ = [
    "AnomalyDetector",
    "Anomaly",
    "AnomalyType",
    "AnomalySeverity",
    "ZScoreDetector",
    "IQRDetector",
    "MovingAverageDetector",
    "AnomalyAlertService",
]
```

### 2. Create `/services/query-service/src/aswa_query/anomaly/models.py`
```python
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
```

### 3. Create `/services/query-service/src/aswa_query/anomaly/algorithms.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import statistics
from typing import Any
import structlog

logger = structlog.get_logger()


@dataclass
class DetectionResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    score: float  # How anomalous (0-1)
    expected_value: float | None = None
    actual_value: float | None = None
    threshold: float | None = None
    method: str = ""


class AnomalyAlgorithm(ABC):
    """Abstract base for anomaly detection algorithms."""

    @abstractmethod
    def detect(self, value: float, history: list[float]) -> DetectionResult:
        """Detect if value is anomalous given history."""
        ...

    @abstractmethod
    def fit(self, data: list[float]) -> None:
        """Fit the algorithm to historical data."""
        ...


class ZScoreDetector(AnomalyAlgorithm):
    """Detect anomalies using Z-score (standard deviations from mean)."""

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        self.mean: float = 0
        self.std: float = 0

    def fit(self, data: list[float]) -> None:
        """Fit to historical data."""
        if len(data) < 2:
            return
        self.mean = statistics.mean(data)
        self.std = statistics.stdev(data)

    def detect(self, value: float, history: list[float]) -> DetectionResult:
        """Detect anomaly using Z-score."""
        if len(history) < 2:
            return DetectionResult(
                is_anomaly=False,
                score=0,
                method="z_score",
            )

        mean = statistics.mean(history)
        std = statistics.stdev(history)

        if std == 0:
            is_anomaly = value != mean
            return DetectionResult(
                is_anomaly=is_anomaly,
                score=1.0 if is_anomaly else 0.0,
                expected_value=mean,
                actual_value=value,
                method="z_score",
            )

        z_score = abs(value - mean) / std
        is_anomaly = z_score > self.threshold
        score = min(z_score / (self.threshold * 2), 1.0)

        return DetectionResult(
            is_anomaly=is_anomaly,
            score=score,
            expected_value=mean,
            actual_value=value,
            threshold=self.threshold,
            method="z_score",
        )


class IQRDetector(AnomalyAlgorithm):
    """Detect anomalies using Interquartile Range."""

    def __init__(self, multiplier: float = 1.5):
        self.multiplier = multiplier
        self.q1: float = 0
        self.q3: float = 0
        self.iqr: float = 0

    def fit(self, data: list[float]) -> None:
        """Fit to historical data."""
        if len(data) < 4:
            return
        sorted_data = sorted(data)
        n = len(sorted_data)
        self.q1 = sorted_data[n // 4]
        self.q3 = sorted_data[3 * n // 4]
        self.iqr = self.q3 - self.q1

    def detect(self, value: float, history: list[float]) -> DetectionResult:
        """Detect anomaly using IQR."""
        if len(history) < 4:
            return DetectionResult(
                is_anomaly=False,
                score=0,
                method="iqr",
            )

        sorted_history = sorted(history)
        n = len(sorted_history)
        q1 = sorted_history[n // 4]
        q3 = sorted_history[3 * n // 4]
        iqr = q3 - q1

        if iqr == 0:
            median = statistics.median(history)
            is_anomaly = value != median
            return DetectionResult(
                is_anomaly=is_anomaly,
                score=1.0 if is_anomaly else 0.0,
                expected_value=median,
                actual_value=value,
                method="iqr",
            )

        lower_bound = q1 - self.multiplier * iqr
        upper_bound = q3 + self.multiplier * iqr

        is_anomaly = value < lower_bound or value > upper_bound

        # Calculate score based on distance from bounds
        if value < lower_bound:
            distance = (lower_bound - value) / iqr
        elif value > upper_bound:
            distance = (value - upper_bound) / iqr
        else:
            distance = 0

        score = min(distance / (self.multiplier * 2), 1.0)

        return DetectionResult(
            is_anomaly=is_anomaly,
            score=score,
            expected_value=statistics.median(history),
            actual_value=value,
            threshold=self.multiplier,
            method="iqr",
        )


class MovingAverageDetector(AnomalyAlgorithm):
    """Detect anomalies using moving average deviation."""

    def __init__(self, window_size: int = 7, threshold: float = 2.0):
        self.window_size = window_size
        self.threshold = threshold

    def fit(self, data: list[float]) -> None:
        """No fitting needed for moving average."""
        pass

    def detect(self, value: float, history: list[float]) -> DetectionResult:
        """Detect anomaly using moving average."""
        if len(history) < self.window_size:
            return DetectionResult(
                is_anomaly=False,
                score=0,
                method="moving_average",
            )

        # Calculate moving average of recent history
        recent = history[-self.window_size:]
        moving_avg = statistics.mean(recent)
        moving_std = statistics.stdev(recent) if len(recent) > 1 else 0

        if moving_std == 0:
            is_anomaly = value != moving_avg
            return DetectionResult(
                is_anomaly=is_anomaly,
                score=1.0 if is_anomaly else 0.0,
                expected_value=moving_avg,
                actual_value=value,
                method="moving_average",
            )

        deviation = abs(value - moving_avg) / moving_std
        is_anomaly = deviation > self.threshold
        score = min(deviation / (self.threshold * 2), 1.0)

        return DetectionResult(
            is_anomaly=is_anomaly,
            score=score,
            expected_value=moving_avg,
            actual_value=value,
            threshold=self.threshold,
            method="moving_average",
        )


class EnsembleDetector(AnomalyAlgorithm):
    """Combine multiple detection algorithms."""

    def __init__(
        self,
        algorithms: list[AnomalyAlgorithm] | None = None,
        voting_threshold: float = 0.5,
    ):
        self.algorithms = algorithms or [
            ZScoreDetector(),
            IQRDetector(),
            MovingAverageDetector(),
        ]
        self.voting_threshold = voting_threshold

    def fit(self, data: list[float]) -> None:
        """Fit all algorithms."""
        for algo in self.algorithms:
            algo.fit(data)

    def detect(self, value: float, history: list[float]) -> DetectionResult:
        """Detect using ensemble voting."""
        results = [algo.detect(value, history) for algo in self.algorithms]

        votes = sum(1 for r in results if r.is_anomaly)
        vote_ratio = votes / len(results)

        is_anomaly = vote_ratio >= self.voting_threshold
        avg_score = statistics.mean(r.score for r in results)

        # Use the result with highest score for details
        best_result = max(results, key=lambda r: r.score)

        return DetectionResult(
            is_anomaly=is_anomaly,
            score=avg_score,
            expected_value=best_result.expected_value,
            actual_value=value,
            method="ensemble",
        )
```

### 4. Create `/services/query-service/src/aswa_query/anomaly/detector.py`
```python
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from .models import Anomaly, AnomalyType, AnomalySeverity, AnomalyStats, AnomalySummary
from .algorithms import (
    AnomalyAlgorithm,
    EnsembleDetector,
    ZScoreDetector,
    DetectionResult,
)

logger = structlog.get_logger()


class AnomalyDetector:
    """Detect anomalies in insight and document patterns."""

    def __init__(
        self,
        settings: Settings,
        algorithm: AnomalyAlgorithm | None = None,
    ):
        self.settings = settings
        self.algorithm = algorithm or EnsembleDetector()
        self._stats: dict[str, AnomalyStats] = {}
        self._history: dict[str, list[float]] = {}
        self._max_history = 100

    async def check_insight_volume(
        self,
        tenant_id: UUID,
        current_count: int,
        period: str = "daily",
    ) -> Anomaly | None:
        """Check if insight volume is anomalous.

        Args:
            tenant_id: Tenant ID
            current_count: Current insight count
            period: Time period (daily, hourly)

        Returns:
            Anomaly if detected, None otherwise
        """
        metric_key = f"{tenant_id}:insight_volume:{period}"
        history = self._get_history(metric_key)

        result = self.algorithm.detect(float(current_count), history)

        # Update history
        self._update_history(metric_key, float(current_count))

        if result.is_anomaly:
            anomaly_type = (
                AnomalyType.VOLUME_SPIKE
                if current_count > (result.expected_value or 0)
                else AnomalyType.VOLUME_DROP
            )

            return self._create_anomaly(
                tenant_id=tenant_id,
                anomaly_type=anomaly_type,
                result=result,
                title=f"Unusual {period} insight volume",
                description=self._describe_volume_anomaly(result, period),
            )

        return None

    async def check_confidence_distribution(
        self,
        tenant_id: UUID,
        avg_confidence: float,
    ) -> Anomaly | None:
        """Check if average confidence is anomalous."""
        metric_key = f"{tenant_id}:avg_confidence"
        history = self._get_history(metric_key)

        result = self.algorithm.detect(avg_confidence, history)
        self._update_history(metric_key, avg_confidence)

        if result.is_anomaly:
            return self._create_anomaly(
                tenant_id=tenant_id,
                anomaly_type=AnomalyType.CONFIDENCE_ANOMALY,
                result=result,
                title="Unusual confidence scores",
                description=f"Average confidence {avg_confidence:.2f} deviates from normal pattern.",
            )

        return None

    async def check_category_distribution(
        self,
        tenant_id: UUID,
        category: str,
        count: int,
    ) -> Anomaly | None:
        """Check if category count is anomalous."""
        metric_key = f"{tenant_id}:category:{category}"
        history = self._get_history(metric_key)

        # Too few data points
        if len(history) < 5:
            self._update_history(metric_key, float(count))
            return None

        result = self.algorithm.detect(float(count), history)
        self._update_history(metric_key, float(count))

        if result.is_anomaly and result.score > 0.7:
            return self._create_anomaly(
                tenant_id=tenant_id,
                anomaly_type=AnomalyType.UNUSUAL_PATTERN,
                result=result,
                title=f"Unusual '{category}' insight count",
                description=f"Category '{category}' count {count} is unusual (expected ~{result.expected_value:.0f}).",
            )

        return None

    async def check_processing_metrics(
        self,
        tenant_id: UUID,
        processing_time_ms: float,
        error_rate: float,
    ) -> list[Anomaly]:
        """Check processing metrics for anomalies."""
        anomalies = []

        # Check processing time
        time_key = f"{tenant_id}:processing_time"
        time_history = self._get_history(time_key)
        time_result = self.algorithm.detect(processing_time_ms, time_history)
        self._update_history(time_key, processing_time_ms)

        if time_result.is_anomaly and processing_time_ms > (time_result.expected_value or 0):
            anomalies.append(self._create_anomaly(
                tenant_id=tenant_id,
                anomaly_type=AnomalyType.PROCESSING_ERROR,
                result=time_result,
                title="Slow processing detected",
                description=f"Processing time {processing_time_ms:.0f}ms is unusually high.",
            ))

        # Check error rate
        error_key = f"{tenant_id}:error_rate"
        error_history = self._get_history(error_key)
        error_result = self.algorithm.detect(error_rate, error_history)
        self._update_history(error_key, error_rate)

        if error_result.is_anomaly and error_rate > (error_result.expected_value or 0):
            anomalies.append(self._create_anomaly(
                tenant_id=tenant_id,
                anomaly_type=AnomalyType.PROCESSING_ERROR,
                result=error_result,
                title="Elevated error rate",
                description=f"Error rate {error_rate:.1%} is above normal.",
                severity=AnomalySeverity.HIGH,
            ))

        return anomalies

    async def get_summary(
        self,
        tenant_id: UUID,
        days: int = 7,
    ) -> AnomalySummary:
        """Get anomaly summary for a tenant."""
        # Would retrieve from storage
        now = datetime.utcnow()
        return AnomalySummary(
            tenant_id=tenant_id,
            period_start=now - timedelta(days=days),
            period_end=now,
        )

    def _get_history(self, key: str) -> list[float]:
        """Get history for a metric."""
        if key not in self._history:
            self._history[key] = []
        return self._history[key]

    def _update_history(self, key: str, value: float) -> None:
        """Update history for a metric."""
        if key not in self._history:
            self._history[key] = []

        self._history[key].append(value)

        # Trim to max size
        if len(self._history[key]) > self._max_history:
            self._history[key] = self._history[key][-self._max_history:]

    def _create_anomaly(
        self,
        tenant_id: UUID,
        anomaly_type: AnomalyType,
        result: DetectionResult,
        title: str,
        description: str,
        severity: AnomalySeverity | None = None,
    ) -> Anomaly:
        """Create an anomaly object."""
        if severity is None:
            severity = self._calculate_severity(result.score)

        return Anomaly(
            tenant_id=tenant_id,
            anomaly_type=anomaly_type,
            severity=severity,
            title=title,
            description=description,
            detection_method=result.method,
            confidence=1 - result.score,  # Invert: higher score = more anomalous
            expected_value=result.expected_value,
            actual_value=result.actual_value,
            deviation=result.score,
        )

    def _calculate_severity(self, score: float) -> AnomalySeverity:
        """Calculate severity from anomaly score."""
        if score >= 0.9:
            return AnomalySeverity.CRITICAL
        elif score >= 0.7:
            return AnomalySeverity.HIGH
        elif score >= 0.5:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _describe_volume_anomaly(
        self,
        result: DetectionResult,
        period: str,
    ) -> str:
        """Generate description for volume anomaly."""
        expected = result.expected_value or 0
        actual = result.actual_value or 0

        if actual > expected:
            pct = ((actual - expected) / expected * 100) if expected > 0 else 100
            return f"Insight volume ({actual:.0f}) is {pct:.0f}% higher than normal ({expected:.0f})."
        else:
            pct = ((expected - actual) / expected * 100) if expected > 0 else 100
            return f"Insight volume ({actual:.0f}) is {pct:.0f}% lower than normal ({expected:.0f})."

    def clear_history(self, tenant_id: UUID | None = None) -> None:
        """Clear detection history."""
        if tenant_id:
            prefix = str(tenant_id)
            self._history = {
                k: v for k, v in self._history.items()
                if not k.startswith(prefix)
            }
        else:
            self._history.clear()
```

### 5. Create `/services/query-service/src/aswa_query/anomaly/alerts.py`
```python
from datetime import datetime
from typing import Any, Callable
from uuid import UUID
import structlog

from .models import Anomaly, AnomalySeverity

logger = structlog.get_logger()


class AnomalyAlertService:
    """Service for managing anomaly alerts."""

    def __init__(
        self,
        alert_callback: Callable[[Anomaly], Any] | None = None,
        min_severity: AnomalySeverity = AnomalySeverity.MEDIUM,
    ):
        self.alert_callback = alert_callback
        self.min_severity = min_severity
        self._severity_order = {
            AnomalySeverity.LOW: 0,
            AnomalySeverity.MEDIUM: 1,
            AnomalySeverity.HIGH: 2,
            AnomalySeverity.CRITICAL: 3,
        }

    async def process_anomaly(self, anomaly: Anomaly) -> bool:
        """Process an anomaly and send alert if needed.

        Args:
            anomaly: Detected anomaly

        Returns:
            True if alert was sent
        """
        if not self._should_alert(anomaly):
            logger.debug(
                "Anomaly below alert threshold",
                anomaly_id=str(anomaly.id),
                severity=anomaly.severity,
            )
            return False

        if self.alert_callback:
            try:
                result = self.alert_callback(anomaly)
                if hasattr(result, '__await__'):
                    await result

                logger.info(
                    "Anomaly alert sent",
                    anomaly_id=str(anomaly.id),
                    severity=anomaly.severity,
                )
                return True

            except Exception as e:
                logger.error("Alert callback failed", error=str(e))
                return False

        return False

    async def process_batch(self, anomalies: list[Anomaly]) -> int:
        """Process multiple anomalies.

        Args:
            anomalies: List of anomalies

        Returns:
            Number of alerts sent
        """
        alerts_sent = 0
        for anomaly in anomalies:
            if await self.process_anomaly(anomaly):
                alerts_sent += 1
        return alerts_sent

    def _should_alert(self, anomaly: Anomaly) -> bool:
        """Check if anomaly should trigger alert."""
        anomaly_level = self._severity_order.get(anomaly.severity, 0)
        min_level = self._severity_order.get(self.min_severity, 1)
        return anomaly_level >= min_level

    def set_min_severity(self, severity: AnomalySeverity) -> None:
        """Set minimum severity for alerts."""
        self.min_severity = severity
```

## Test Requirements

### Create `/services/query-service/tests/anomaly/test_algorithms.py`
```python
import pytest
from aswa_query.anomaly.algorithms import (
    ZScoreDetector,
    IQRDetector,
    MovingAverageDetector,
    EnsembleDetector,
)


class TestZScoreDetector:
    def test_detect_normal(self):
        """Test normal value detection."""
        detector = ZScoreDetector(threshold=2.0)
        history = [10, 11, 9, 10, 11, 10, 9, 11]

        result = detector.detect(10.5, history)

        assert result.is_anomaly is False

    def test_detect_anomaly(self):
        """Test anomaly detection."""
        detector = ZScoreDetector(threshold=2.0)
        history = [10, 11, 9, 10, 11, 10, 9, 11]

        result = detector.detect(50, history)

        assert result.is_anomaly is True
        assert result.score > 0.5


class TestIQRDetector:
    def test_detect_within_bounds(self):
        """Test value within IQR bounds."""
        detector = IQRDetector()
        history = list(range(1, 21))

        result = detector.detect(10, history)

        assert result.is_anomaly is False

    def test_detect_outlier(self):
        """Test outlier detection."""
        detector = IQRDetector()
        history = list(range(1, 21))

        result = detector.detect(100, history)

        assert result.is_anomaly is True


class TestEnsembleDetector:
    def test_consensus_detection(self):
        """Test ensemble voting."""
        detector = EnsembleDetector()
        history = [10, 11, 9, 10, 11, 10, 9, 11]

        # Normal value
        result = detector.detect(10, history)
        assert result.is_anomaly is False

        # Clear anomaly
        result = detector.detect(100, history)
        assert result.is_anomaly is True
```

### Create `/services/query-service/tests/anomaly/test_detector.py`
```python
import pytest
from uuid import uuid4

from aswa_query.anomaly.detector import AnomalyDetector
from aswa_query.anomaly.models import AnomalyType
from aswa_query.config import Settings


class TestAnomalyDetector:
    @pytest.fixture
    def detector(self):
        return AnomalyDetector(Settings())

    @pytest.mark.asyncio
    async def test_check_insight_volume_normal(self, detector):
        """Test normal volume check."""
        tenant_id = uuid4()

        # Build history
        for i in range(10):
            detector._update_history(f"{tenant_id}:insight_volume:daily", 100.0)

        result = await detector.check_insight_volume(tenant_id, 105)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_insight_volume_spike(self, detector):
        """Test volume spike detection."""
        tenant_id = uuid4()

        # Build stable history
        for i in range(10):
            detector._update_history(f"{tenant_id}:insight_volume:daily", 100.0)

        # Spike
        result = await detector.check_insight_volume(tenant_id, 500)

        assert result is not None
        assert result.anomaly_type == AnomalyType.VOLUME_SPIKE

    @pytest.mark.asyncio
    async def test_check_processing_metrics(self, detector):
        """Test processing metrics check."""
        tenant_id = uuid4()

        # Build history
        for i in range(10):
            detector._update_history(f"{tenant_id}:processing_time", 100.0)
            detector._update_history(f"{tenant_id}:error_rate", 0.01)

        # Normal metrics
        anomalies = await detector.check_processing_metrics(tenant_id, 110, 0.02)
        assert len(anomalies) == 0

        # Anomalous metrics
        anomalies = await detector.check_processing_metrics(tenant_id, 10000, 0.5)
        assert len(anomalies) >= 1
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/anomaly/ -v`
2. Verify imports: `python -c "from aswa_query.anomaly import AnomalyDetector"`
