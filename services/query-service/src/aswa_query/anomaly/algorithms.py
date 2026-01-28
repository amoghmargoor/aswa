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
