import pytest
from datetime import datetime, timedelta

from aswa_query.trends.analyzer import TimeSeriesAnalyzer, TimeSeriesPoint


class TestTimeSeriesAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return TimeSeriesAnalyzer()

    def test_detect_increasing_trend(self, analyzer):
        """Test detection of increasing trend."""
        data = [
            TimeSeriesPoint(datetime.now() - timedelta(days=i), float(10 + i))
            for i in range(10, -1, -1)
        ]

        trend_type, confidence = analyzer.detect_trend_type(data)

        assert trend_type == "increasing"
        assert confidence > 0.5

    def test_detect_decreasing_trend(self, analyzer):
        """Test detection of decreasing trend."""
        data = [
            TimeSeriesPoint(datetime.now() - timedelta(days=i), float(20 - i))
            for i in range(10, -1, -1)
        ]

        trend_type, confidence = analyzer.detect_trend_type(data)

        assert trend_type == "decreasing"

    def test_detect_stable_trend(self, analyzer):
        """Test detection of stable trend."""
        data = [
            TimeSeriesPoint(datetime.now() - timedelta(days=i), 10.0)
            for i in range(10, -1, -1)
        ]

        trend_type, confidence = analyzer.detect_trend_type(data)

        assert trend_type == "stable"

    def test_calculate_strength(self, analyzer):
        """Test strength calculation."""
        # Strong trend: 100% increase
        strong_data = [
            TimeSeriesPoint(datetime.now() - timedelta(days=i), float(10 + i * 2))
            for i in range(10, -1, -1)
        ]

        strength = analyzer.calculate_strength(strong_data)
        assert strength in ["moderate", "strong"]

    def test_forecast(self, analyzer):
        """Test forecasting."""
        data = [
            TimeSeriesPoint(datetime.now() - timedelta(days=i), float(10 + i))
            for i in range(10, -1, -1)
        ]

        forecast = analyzer.forecast(data, periods=5)

        assert len(forecast) == 5
        assert all(f["is_forecast"] for f in forecast)
