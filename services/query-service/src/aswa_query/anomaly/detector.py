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
