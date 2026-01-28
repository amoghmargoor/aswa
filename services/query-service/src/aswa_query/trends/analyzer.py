from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
import statistics
import structlog

logger = structlog.get_logger()


@dataclass
class TimeSeriesPoint:
    """A point in a time series."""
    timestamp: datetime
    value: float
    label: str | None = None


class TimeSeriesAnalyzer:
    """Analyze time series data for trends."""

    def __init__(self, min_data_points: int = 5):
        self.min_data_points = min_data_points

    def detect_trend_type(
        self,
        data_points: list[TimeSeriesPoint],
    ) -> tuple[str, float]:
        """Detect the type of trend in data.

        Args:
            data_points: Time series data

        Returns:
            Tuple of (trend_type, confidence)
        """
        if len(data_points) < self.min_data_points:
            return "stable", 0.5

        values = [p.value for p in data_points]

        # Calculate linear regression slope
        slope = self._calculate_slope(values)
        r_squared = self._calculate_r_squared(values)
        volatility = self._calculate_volatility(values)

        # Determine trend type
        if volatility > 0.5:
            return "volatile", 0.7
        elif abs(slope) < 0.1:
            return "stable", 0.8
        elif slope > 0.3:
            return "increasing", min(0.5 + r_squared * 0.5, 1.0)
        elif slope < -0.3:
            return "decreasing", min(0.5 + r_squared * 0.5, 1.0)
        else:
            return "stable", 0.6

    def calculate_strength(
        self,
        data_points: list[TimeSeriesPoint],
    ) -> str:
        """Calculate trend strength.

        Args:
            data_points: Time series data

        Returns:
            Trend strength ("weak", "moderate", "strong")
        """
        if len(data_points) < 2:
            return "weak"

        values = [p.value for p in data_points]

        # Calculate percentage change
        if values[0] == 0:
            pct_change = 0 if values[-1] == 0 else 100
        else:
            pct_change = abs((values[-1] - values[0]) / values[0] * 100)

        # Calculate consistency
        r_squared = self._calculate_r_squared(values)

        if pct_change > 50 and r_squared > 0.7:
            return "strong"
        elif pct_change > 20 or r_squared > 0.5:
            return "moderate"
        else:
            return "weak"

    def detect_seasonality(
        self,
        data_points: list[TimeSeriesPoint],
        period: int = 7,  # Weekly by default
    ) -> tuple[bool, float]:
        """Detect seasonal patterns.

        Args:
            data_points: Time series data
            period: Expected seasonality period

        Returns:
            Tuple of (is_seasonal, confidence)
        """
        if len(data_points) < period * 2:
            return False, 0.0

        values = [p.value for p in data_points]

        # Calculate autocorrelation at the given period
        autocorr = self._autocorrelation(values, period)

        is_seasonal = autocorr > 0.5
        confidence = min(abs(autocorr), 1.0)

        return is_seasonal, confidence

    def forecast(
        self,
        data_points: list[TimeSeriesPoint],
        periods: int = 7,
    ) -> list[dict]:
        """Forecast future values.

        Args:
            data_points: Historical data
            periods: Number of periods to forecast

        Returns:
            List of forecasted points
        """
        if len(data_points) < self.min_data_points:
            return []

        values = [p.value for p in data_points]

        # Simple linear extrapolation
        slope = self._calculate_slope(values)
        last_value = values[-1]
        last_time = data_points[-1].timestamp

        forecasts = []
        for i in range(1, periods + 1):
            forecast_value = last_value + slope * i
            forecast_time = last_time + timedelta(days=i)
            forecasts.append({
                "timestamp": forecast_time.isoformat(),
                "value": max(0, forecast_value),  # No negative values
                "is_forecast": True,
            })

        return forecasts

    def detect_change_points(
        self,
        data_points: list[TimeSeriesPoint],
        threshold: float = 2.0,
    ) -> list[int]:
        """Detect significant change points in the series.

        Args:
            data_points: Time series data
            threshold: Standard deviation threshold

        Returns:
            List of indices where changes occur
        """
        if len(data_points) < 3:
            return []

        values = [p.value for p in data_points]
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        if std == 0:
            return []

        change_points = []
        for i in range(1, len(values)):
            diff = abs(values[i] - values[i-1])
            if diff > threshold * std:
                change_points.append(i)

        return change_points

    def _calculate_slope(self, values: list[float]) -> float:
        """Calculate normalized slope of values."""
        n = len(values)
        if n < 2:
            return 0

        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0

        slope = numerator / denominator

        # Normalize by value range
        value_range = max(values) - min(values) if max(values) != min(values) else 1
        return slope / value_range

    def _calculate_r_squared(self, values: list[float]) -> float:
        """Calculate R-squared for linear fit."""
        n = len(values)
        if n < 2:
            return 0

        y_mean = statistics.mean(values)
        slope = self._calculate_slope(values) * (max(values) - min(values) if max(values) != min(values) else 1)
        intercept = y_mean - slope * (n - 1) / 2

        predicted = [intercept + slope * i for i in range(n)]

        ss_res = sum((v - p) ** 2 for v, p in zip(values, predicted))
        ss_tot = sum((v - y_mean) ** 2 for v in values)

        if ss_tot == 0:
            return 1.0

        return 1 - (ss_res / ss_tot)

    def _calculate_volatility(self, values: list[float]) -> float:
        """Calculate volatility (coefficient of variation)."""
        if len(values) < 2:
            return 0

        mean = statistics.mean(values)
        if mean == 0:
            return 0

        std = statistics.stdev(values)
        return std / abs(mean)

    def _autocorrelation(self, values: list[float], lag: int) -> float:
        """Calculate autocorrelation at given lag."""
        n = len(values)
        if n <= lag:
            return 0

        mean = statistics.mean(values)
        variance = statistics.variance(values) if len(values) > 1 else 0

        if variance == 0:
            return 0

        covariance = sum(
            (values[i] - mean) * (values[i + lag] - mean)
            for i in range(n - lag)
        ) / (n - lag)

        return covariance / variance
