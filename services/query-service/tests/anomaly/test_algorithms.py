"""Tests for anomaly detection algorithms."""
import pytest
import statistics

from aswa_query.anomaly.algorithms import (
    DetectionResult,
    ZScoreDetector,
    IQRDetector,
    MovingAverageDetector,
    EnsembleDetector,
)


class TestZScoreDetector:
    """Tests for Z-score anomaly detection."""

    def test_detect_no_history(self):
        """Should return no anomaly when history is insufficient."""
        detector = ZScoreDetector()
        result = detector.detect(100, [])

        assert not result.is_anomaly
        assert result.score == 0
        assert result.method == "z_score"

    def test_detect_normal_value(self):
        """Should not flag normal values."""
        detector = ZScoreDetector(threshold=3.0)
        history = [100, 102, 98, 101, 99, 100, 103, 97]

        result = detector.detect(101, history)

        assert not result.is_anomaly
        assert result.score < 0.5

    def test_detect_anomaly(self):
        """Should flag anomalous values."""
        detector = ZScoreDetector(threshold=2.0)
        history = [100, 102, 98, 101, 99, 100, 103, 97]

        # Value far from mean
        result = detector.detect(150, history)

        assert result.is_anomaly
        assert result.score > 0.5
        assert result.expected_value is not None
        assert result.actual_value == 150

    def test_detect_zero_std(self):
        """Should handle zero standard deviation."""
        detector = ZScoreDetector()
        history = [100, 100, 100, 100]

        # Same as history
        result = detector.detect(100, history)
        assert not result.is_anomaly

        # Different from history
        result = detector.detect(101, history)
        assert result.is_anomaly
        assert result.score == 1.0

    def test_fit(self):
        """Should fit to historical data."""
        detector = ZScoreDetector()
        data = [10, 20, 30, 40, 50]

        detector.fit(data)

        assert detector.mean == statistics.mean(data)
        assert detector.std == statistics.stdev(data)


class TestIQRDetector:
    """Tests for IQR anomaly detection."""

    def test_detect_no_history(self):
        """Should return no anomaly when history is insufficient."""
        detector = IQRDetector()
        result = detector.detect(100, [1, 2, 3])

        assert not result.is_anomaly
        assert result.method == "iqr"

    def test_detect_normal_value(self):
        """Should not flag values within IQR bounds."""
        detector = IQRDetector(multiplier=1.5)
        history = [10, 20, 30, 40, 50, 60, 70, 80]

        result = detector.detect(45, history)

        assert not result.is_anomaly
        assert result.score == 0

    def test_detect_outlier_high(self):
        """Should flag high outliers."""
        detector = IQRDetector(multiplier=1.5)
        history = [10, 20, 30, 40, 50, 60, 70, 80]

        result = detector.detect(200, history)

        assert result.is_anomaly
        assert result.score > 0

    def test_detect_outlier_low(self):
        """Should flag low outliers."""
        detector = IQRDetector(multiplier=1.5)
        history = [10, 20, 30, 40, 50, 60, 70, 80]

        result = detector.detect(-100, history)

        assert result.is_anomaly
        assert result.score > 0

    def test_detect_zero_iqr(self):
        """Should handle zero IQR."""
        detector = IQRDetector()
        history = [50, 50, 50, 50, 50, 50, 50, 50]

        result = detector.detect(50, history)
        assert not result.is_anomaly

        result = detector.detect(51, history)
        assert result.is_anomaly


class TestMovingAverageDetector:
    """Tests for moving average anomaly detection."""

    def test_detect_insufficient_history(self):
        """Should return no anomaly when history is insufficient."""
        detector = MovingAverageDetector(window_size=7)
        result = detector.detect(100, [1, 2, 3])

        assert not result.is_anomaly
        assert result.method == "moving_average"

    def test_detect_normal_value(self):
        """Should not flag normal values."""
        detector = MovingAverageDetector(window_size=5, threshold=2.0)
        history = [100, 102, 98, 101, 99, 100, 103]

        result = detector.detect(101, history)

        assert not result.is_anomaly

    def test_detect_anomaly(self):
        """Should flag values far from moving average."""
        detector = MovingAverageDetector(window_size=5, threshold=2.0)
        history = [100, 102, 98, 101, 99, 100, 103]

        result = detector.detect(150, history)

        assert result.is_anomaly
        assert result.expected_value is not None

    def test_uses_recent_window(self):
        """Should use only recent values for detection."""
        detector = MovingAverageDetector(window_size=3, threshold=2.0)
        # Old values are low, recent values are high
        history = [10, 10, 10, 10, 100, 100, 100]

        result = detector.detect(100, history)

        # 100 should match recent moving average
        assert not result.is_anomaly


class TestEnsembleDetector:
    """Tests for ensemble anomaly detection."""

    def test_detect_with_defaults(self):
        """Should use default algorithms."""
        detector = EnsembleDetector()
        history = [100, 102, 98, 101, 99, 100, 103, 97]

        result = detector.detect(100, history)

        assert result.method == "ensemble"
        assert 0 <= result.score <= 1

    def test_detect_clear_anomaly(self):
        """Should detect clear anomalies with consensus."""
        detector = EnsembleDetector(voting_threshold=0.5)
        history = [100, 102, 98, 101, 99, 100, 103, 97]

        result = detector.detect(500, history)

        assert result.is_anomaly
        assert result.score > 0.5

    def test_detect_borderline_case(self):
        """Should handle borderline cases based on voting."""
        detector = EnsembleDetector(voting_threshold=0.5)
        history = [100, 102, 98, 101, 99, 100, 103, 97]

        # Slightly elevated but not extreme
        result = detector.detect(115, history)

        # Result depends on algorithm consensus
        assert result.method == "ensemble"
        assert result.actual_value == 115

    def test_fit_all_algorithms(self):
        """Should fit all algorithms."""
        z_detector = ZScoreDetector()
        iqr_detector = IQRDetector()
        detector = EnsembleDetector(algorithms=[z_detector, iqr_detector])

        data = [10, 20, 30, 40, 50]
        detector.fit(data)

        # Verify algorithms were fitted
        assert z_detector.mean == statistics.mean(data)

    def test_custom_algorithms(self):
        """Should work with custom algorithm list."""
        detector = EnsembleDetector(
            algorithms=[ZScoreDetector(threshold=2.0)],
            voting_threshold=0.5,
        )

        history = [100, 102, 98, 101, 99, 100, 103, 97]
        result = detector.detect(100, history)

        assert result.method == "ensemble"


class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_create_result(self):
        """Should create detection result."""
        result = DetectionResult(
            is_anomaly=True,
            score=0.85,
            expected_value=100.0,
            actual_value=150.0,
            threshold=3.0,
            method="z_score",
        )

        assert result.is_anomaly
        assert result.score == 0.85
        assert result.expected_value == 100.0
        assert result.actual_value == 150.0
        assert result.threshold == 3.0
        assert result.method == "z_score"

    def test_default_values(self):
        """Should have sensible defaults."""
        result = DetectionResult(is_anomaly=False, score=0.0)

        assert result.expected_value is None
        assert result.actual_value is None
        assert result.threshold is None
        assert result.method == ""
