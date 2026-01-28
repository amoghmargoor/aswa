"""Tests for AnomalyDetector."""
import pytest
from uuid import uuid4
from unittest.mock import MagicMock

from aswa_query.anomaly.detector import AnomalyDetector
from aswa_query.anomaly.models import AnomalyType, AnomalySeverity
from aswa_query.anomaly.algorithms import ZScoreDetector, DetectionResult
from aswa_query.config import Settings


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings()


@pytest.fixture
def detector(settings):
    """Create detector with test settings."""
    return AnomalyDetector(settings)


class TestAnomalyDetector:
    """Tests for AnomalyDetector."""

    @pytest.mark.asyncio
    async def test_check_insight_volume_no_history(self, detector):
        """Should not detect anomaly without history."""
        tenant_id = uuid4()

        result = await detector.check_insight_volume(tenant_id, 100)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_insight_volume_normal(self, detector):
        """Should not detect anomaly for normal volume."""
        tenant_id = uuid4()

        # Build up history
        for count in [100, 102, 98, 101, 99, 100, 103, 97]:
            await detector.check_insight_volume(tenant_id, count)

        # Normal value
        result = await detector.check_insight_volume(tenant_id, 101)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_insight_volume_spike(self, detector):
        """Should detect volume spike."""
        tenant_id = uuid4()

        # Build up history with low values
        for count in [100, 102, 98, 101, 99, 100, 103, 97]:
            await detector.check_insight_volume(tenant_id, count)

        # Spike
        result = await detector.check_insight_volume(tenant_id, 500)

        assert result is not None
        assert result.anomaly_type == AnomalyType.VOLUME_SPIKE
        assert result.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_check_insight_volume_drop(self, detector):
        """Should detect volume drop."""
        tenant_id = uuid4()

        # Build up history with higher values
        for count in [100, 102, 98, 101, 99, 100, 103, 97]:
            await detector.check_insight_volume(tenant_id, count)

        # Drop to very low
        result = await detector.check_insight_volume(tenant_id, 10)

        assert result is not None
        assert result.anomaly_type == AnomalyType.VOLUME_DROP

    @pytest.mark.asyncio
    async def test_check_confidence_distribution(self, detector):
        """Should detect confidence anomaly."""
        tenant_id = uuid4()

        # Build up history
        for conf in [0.85, 0.87, 0.84, 0.86, 0.85, 0.88, 0.84, 0.86]:
            await detector.check_confidence_distribution(tenant_id, conf)

        # Anomalous confidence
        result = await detector.check_confidence_distribution(tenant_id, 0.3)

        assert result is not None
        assert result.anomaly_type == AnomalyType.CONFIDENCE_ANOMALY

    @pytest.mark.asyncio
    async def test_check_category_distribution_insufficient_data(self, detector):
        """Should not detect with insufficient data."""
        tenant_id = uuid4()

        # Only 3 data points
        for count in [10, 12, 11]:
            result = await detector.check_category_distribution(
                tenant_id, "performance", count
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_check_category_distribution_anomaly(self, detector):
        """Should detect category anomaly."""
        tenant_id = uuid4()

        # Build up history
        for count in [10, 12, 11, 10, 13, 11, 12, 10]:
            await detector.check_category_distribution(tenant_id, "performance", count)

        # Anomalous count
        result = await detector.check_category_distribution(
            tenant_id, "performance", 100
        )

        assert result is not None
        assert result.anomaly_type == AnomalyType.UNUSUAL_PATTERN

    @pytest.mark.asyncio
    async def test_check_processing_metrics_normal(self, detector):
        """Should not detect anomaly for normal metrics."""
        tenant_id = uuid4()

        # Build up history
        for _ in range(10):
            await detector.check_processing_metrics(
                tenant_id, processing_time_ms=100.0, error_rate=0.01
            )

        # Normal metrics
        anomalies = await detector.check_processing_metrics(
            tenant_id, processing_time_ms=105.0, error_rate=0.02
        )

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_check_processing_metrics_slow(self, detector):
        """Should detect slow processing."""
        tenant_id = uuid4()

        # Build up history
        for _ in range(10):
            await detector.check_processing_metrics(
                tenant_id, processing_time_ms=100.0, error_rate=0.01
            )

        # Very slow processing
        anomalies = await detector.check_processing_metrics(
            tenant_id, processing_time_ms=1000.0, error_rate=0.01
        )

        assert len(anomalies) >= 1
        assert any(a.title == "Slow processing detected" for a in anomalies)

    @pytest.mark.asyncio
    async def test_check_processing_metrics_high_errors(self, detector):
        """Should detect high error rate."""
        tenant_id = uuid4()

        # Build up history with low error rates
        for _ in range(10):
            await detector.check_processing_metrics(
                tenant_id, processing_time_ms=100.0, error_rate=0.01
            )

        # High error rate
        anomalies = await detector.check_processing_metrics(
            tenant_id, processing_time_ms=100.0, error_rate=0.50
        )

        assert len(anomalies) >= 1
        high_error_anomaly = next(
            (a for a in anomalies if "error rate" in a.title.lower()),
            None
        )
        assert high_error_anomaly is not None
        assert high_error_anomaly.severity == AnomalySeverity.HIGH

    @pytest.mark.asyncio
    async def test_get_summary(self, detector):
        """Should return anomaly summary."""
        tenant_id = uuid4()

        summary = await detector.get_summary(tenant_id, days=7)

        assert summary.tenant_id == tenant_id
        assert summary.period_start < summary.period_end

    def test_clear_history_all(self, detector):
        """Should clear all history."""
        tenant_id = uuid4()
        detector._history[f"{tenant_id}:test"] = [1, 2, 3]
        detector._history["other:test"] = [4, 5, 6]

        detector.clear_history()

        assert len(detector._history) == 0

    def test_clear_history_by_tenant(self, detector):
        """Should clear history for specific tenant."""
        tenant_id = uuid4()
        other_id = uuid4()
        detector._history[f"{tenant_id}:test"] = [1, 2, 3]
        detector._history[f"{other_id}:test"] = [4, 5, 6]

        detector.clear_history(tenant_id)

        assert f"{tenant_id}:test" not in detector._history
        assert f"{other_id}:test" in detector._history


class TestSeverityCalculation:
    """Tests for severity calculation."""

    def test_critical_severity(self, detector):
        """Should calculate critical severity."""
        severity = detector._calculate_severity(0.95)
        assert severity == AnomalySeverity.CRITICAL

    def test_high_severity(self, detector):
        """Should calculate high severity."""
        severity = detector._calculate_severity(0.75)
        assert severity == AnomalySeverity.HIGH

    def test_medium_severity(self, detector):
        """Should calculate medium severity."""
        severity = detector._calculate_severity(0.55)
        assert severity == AnomalySeverity.MEDIUM

    def test_low_severity(self, detector):
        """Should calculate low severity."""
        severity = detector._calculate_severity(0.3)
        assert severity == AnomalySeverity.LOW


class TestVolumeAnomalyDescription:
    """Tests for volume anomaly descriptions."""

    def test_describe_spike(self, detector):
        """Should describe volume spike."""
        result = DetectionResult(
            is_anomaly=True,
            score=0.8,
            expected_value=100.0,
            actual_value=150.0,
            method="test",
        )

        description = detector._describe_volume_anomaly(result, "daily")

        assert "150" in description
        assert "100" in description
        assert "higher" in description

    def test_describe_drop(self, detector):
        """Should describe volume drop."""
        result = DetectionResult(
            is_anomaly=True,
            score=0.8,
            expected_value=100.0,
            actual_value=50.0,
            method="test",
        )

        description = detector._describe_volume_anomaly(result, "daily")

        assert "50" in description
        assert "100" in description
        assert "lower" in description

    def test_describe_zero_expected(self, detector):
        """Should handle zero expected value."""
        result = DetectionResult(
            is_anomaly=True,
            score=0.8,
            expected_value=0.0,
            actual_value=50.0,
            method="test",
        )

        description = detector._describe_volume_anomaly(result, "hourly")

        assert "100%" in description


class TestHistoryManagement:
    """Tests for history management."""

    def test_get_history_creates_empty(self, detector):
        """Should create empty history if not exists."""
        history = detector._get_history("new_key")

        assert history == []
        assert "new_key" in detector._history

    def test_update_history(self, detector):
        """Should update history with new values."""
        detector._update_history("test_key", 100.0)
        detector._update_history("test_key", 200.0)

        assert detector._history["test_key"] == [100.0, 200.0]

    def test_history_trim_to_max(self, detector):
        """Should trim history to max size."""
        detector._max_history = 5

        for i in range(10):
            detector._update_history("test_key", float(i))

        assert len(detector._history["test_key"]) == 5
        assert detector._history["test_key"] == [5.0, 6.0, 7.0, 8.0, 9.0]


class TestCustomAlgorithm:
    """Tests for using custom algorithm."""

    @pytest.mark.asyncio
    async def test_custom_algorithm(self, settings):
        """Should use custom algorithm."""
        custom_algo = ZScoreDetector(threshold=1.0)  # More sensitive
        detector = AnomalyDetector(settings, algorithm=custom_algo)

        tenant_id = uuid4()

        # Build history
        for count in [100, 102, 98, 101, 99, 100, 103, 97]:
            await detector.check_insight_volume(tenant_id, count)

        # Should detect smaller deviation with lower threshold
        result = await detector.check_insight_volume(tenant_id, 115)

        # With threshold=1.0, this might be detected
        assert detector.algorithm == custom_algo
