# Task 4.3.2: Trend Detection Service

## Context

You are working on the ASWA query-service at `/services/query-service/`. The digest generation is complete. Now we need to detect trends in the insights over time.

## Objective

Create a trend detection service that:
1. Analyzes insight patterns over time
2. Detects emerging trends and declining patterns
3. Identifies seasonal patterns
4. Provides trend forecasting
5. Alerts on significant trend changes

## Requirements

### 1. Create `/services/query-service/src/aswa_query/trends/__init__.py`
```python
from .detector import TrendDetector
from .models import Trend, TrendType, TrendStrength, TrendAlert
from .analyzer import TimeSeriesAnalyzer
from .alerts import TrendAlertService

__all__ = [
    "TrendDetector",
    "Trend",
    "TrendType",
    "TrendStrength",
    "TrendAlert",
    "TimeSeriesAnalyzer",
    "TrendAlertService",
]
```

### 2. Create `/services/query-service/src/aswa_query/trends/models.py`
```python
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
```

### 3. Create `/services/query-service/src/aswa_query/trends/analyzer.py`
```python
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
```

### 4. Create `/services/query-service/src/aswa_query/trends/detector.py`
```python
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from aswa_query.services.insight_client import InsightClient
from .models import Trend, TrendType, TrendStrength, TrendCategory, TrendSummary
from .analyzer import TimeSeriesAnalyzer, TimeSeriesPoint

logger = structlog.get_logger()


class TrendDetector:
    """Detect trends in insights over time."""

    def __init__(
        self,
        settings: Settings,
        insight_client: InsightClient,
        analyzer: TimeSeriesAnalyzer | None = None,
    ):
        self.settings = settings
        self.insight_client = insight_client
        self.analyzer = analyzer or TimeSeriesAnalyzer()

    async def detect_trends(
        self,
        tenant_id: UUID,
        days: int = 30,
        categories: list[TrendCategory] | None = None,
    ) -> list[Trend]:
        """Detect all trends for a tenant.

        Args:
            tenant_id: Tenant ID
            days: Number of days to analyze
            categories: Categories to analyze

        Returns:
            List of detected trends
        """
        categories = categories or list(TrendCategory)
        all_trends = []

        for category in categories:
            trends = await self._detect_category_trends(
                tenant_id, category, days
            )
            all_trends.extend(trends)

        # Sort by strength and confidence
        all_trends.sort(
            key=lambda t: (
                t.strength == TrendStrength.STRONG,
                t.confidence
            ),
            reverse=True
        )

        logger.info(
            "Trends detected",
            tenant_id=str(tenant_id),
            total=len(all_trends),
        )

        return all_trends

    async def _detect_category_trends(
        self,
        tenant_id: UUID,
        category: TrendCategory,
        days: int,
    ) -> list[Trend]:
        """Detect trends for a specific category."""
        # Get historical data
        data = await self._get_historical_data(tenant_id, category, days)

        if not data:
            return []

        trends = []

        # Analyze overall trend
        trend = self._analyze_series(
            tenant_id=tenant_id,
            name=f"{category.value.title()} Trend",
            category=category,
            data_points=data,
            days=days,
        )
        if trend:
            trends.append(trend)

        # Detect subtopic trends
        subtopic_trends = await self._detect_subtopic_trends(
            tenant_id, category, days
        )
        trends.extend(subtopic_trends)

        return trends

    async def _get_historical_data(
        self,
        tenant_id: UUID,
        category: TrendCategory,
        days: int,
    ) -> list[TimeSeriesPoint]:
        """Get historical insight counts by day."""
        # Map category to insight type
        type_map = {
            TrendCategory.RISK: "risk",
            TrendCategory.OPPORTUNITY: "opportunity",
            TrendCategory.ENTITY: "entity",
        }

        insight_type = type_map.get(category)
        if not insight_type:
            return []

        try:
            # Get insights grouped by day
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # This would query insight-engine for daily counts
            # Simulated data for now
            data_points = []
            for i in range(days):
                date = start_date + timedelta(days=i)
                # Would be actual count from database
                value = 10 + i * 0.5  # Simulated increasing trend
                data_points.append(TimeSeriesPoint(
                    timestamp=date,
                    value=value,
                ))

            return data_points

        except Exception as e:
            logger.error("Failed to get historical data", error=str(e))
            return []

    def _analyze_series(
        self,
        tenant_id: UUID,
        name: str,
        category: TrendCategory,
        data_points: list[TimeSeriesPoint],
        days: int,
    ) -> Trend | None:
        """Analyze a time series and create trend."""
        if not data_points:
            return None

        # Detect trend type
        trend_type, confidence = self.analyzer.detect_trend_type(data_points)

        # Calculate strength
        strength = self.analyzer.calculate_strength(data_points)

        # Skip weak, low-confidence trends
        if strength == "weak" and confidence < 0.6:
            return None

        values = [p.value for p in data_points]

        # Create forecast
        forecast = self.analyzer.forecast(data_points, periods=7)

        return Trend(
            tenant_id=tenant_id,
            name=name,
            description=self._generate_description(name, trend_type, values),
            category=category,
            trend_type=TrendType(trend_type),
            strength=TrendStrength(strength),
            confidence=confidence,
            start_date=data_points[0].timestamp,
            end_date=data_points[-1].timestamp,
            data_points=[
                {"timestamp": p.timestamp.isoformat(), "value": p.value}
                for p in data_points
            ],
            change_percentage=self._calc_change_pct(values),
            baseline_value=values[0],
            current_value=values[-1],
            peak_value=max(values),
            forecast=forecast,
            forecast_confidence=0.6,
        )

    async def _detect_subtopic_trends(
        self,
        tenant_id: UUID,
        category: TrendCategory,
        days: int,
    ) -> list[Trend]:
        """Detect trends in specific subtopics."""
        # Would query for top topics/entities and analyze each
        return []

    def _generate_description(
        self,
        name: str,
        trend_type: str,
        values: list[float],
    ) -> str:
        """Generate human-readable trend description."""
        pct_change = self._calc_change_pct(values)
        direction = "increased" if pct_change > 0 else "decreased"

        if trend_type == "increasing":
            return f"{name} has been steadily increasing, up {abs(pct_change):.1f}% over the period."
        elif trend_type == "decreasing":
            return f"{name} has been declining, down {abs(pct_change):.1f}% over the period."
        elif trend_type == "volatile":
            return f"{name} has shown high volatility with frequent changes."
        else:
            return f"{name} has remained relatively stable over the period."

    def _calc_change_pct(self, values: list[float]) -> float:
        """Calculate percentage change."""
        if not values or values[0] == 0:
            return 0
        return ((values[-1] - values[0]) / values[0]) * 100

    async def get_trend_summary(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> TrendSummary:
        """Get summary of all trends."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        trends = await self.detect_trends(tenant_id, days)

        return TrendSummary(
            tenant_id=tenant_id,
            period_start=start_date,
            period_end=end_date,
            total_trends=len(trends),
            increasing_trends=len([t for t in trends if t.trend_type == TrendType.INCREASING]),
            decreasing_trends=len([t for t in trends if t.trend_type == TrendType.DECREASING]),
            emerging_trends=len([t for t in trends if t.trend_type == TrendType.EMERGING]),
            top_trends=trends[:10],
        )
```

### 5. Create `/services/query-service/src/aswa_query/trends/alerts.py`
```python
from datetime import datetime
from typing import Any, Callable
from uuid import UUID
import structlog

from .models import Trend, TrendAlert, TrendType, TrendStrength

logger = structlog.get_logger()


class TrendAlertService:
    """Service for managing trend alerts."""

    def __init__(
        self,
        alert_callback: Callable[[TrendAlert], Any] | None = None,
    ):
        self.alert_callback = alert_callback
        self._previous_trends: dict[str, Trend] = {}
        self._thresholds = {
            "change_pct": 25.0,  # Alert on >25% change
            "confidence": 0.7,   # Minimum confidence for alerts
        }

    async def check_and_alert(
        self,
        trends: list[Trend],
    ) -> list[TrendAlert]:
        """Check trends and generate alerts.

        Args:
            trends: Current trends

        Returns:
            List of generated alerts
        """
        alerts = []

        for trend in trends:
            trend_alerts = self._check_trend(trend)
            alerts.extend(trend_alerts)

            # Update previous trends
            self._previous_trends[str(trend.id)] = trend

        # Send alerts via callback
        if self.alert_callback and alerts:
            for alert in alerts:
                try:
                    await self.alert_callback(alert)
                except Exception as e:
                    logger.error("Alert callback failed", error=str(e))

        return alerts

    def _check_trend(self, trend: Trend) -> list[TrendAlert]:
        """Check a single trend for alert conditions."""
        alerts = []

        # Skip low confidence trends
        if trend.confidence < self._thresholds["confidence"]:
            return alerts

        previous = self._previous_trends.get(str(trend.id))

        # New emerging trend
        if not previous and trend.trend_type == TrendType.EMERGING:
            alerts.append(self._create_alert(
                trend=trend,
                alert_type="new_trend",
                severity=self._calculate_severity(trend),
                title=f"New Emerging Trend: {trend.name}",
                description=trend.description,
            ))

        # Significant change in existing trend
        if previous:
            change = abs(trend.change_percentage - previous.change_percentage)
            if change > self._thresholds["change_pct"]:
                direction = "accelerated" if trend.change_percentage > previous.change_percentage else "reversed"
                alerts.append(self._create_alert(
                    trend=trend,
                    alert_type="trend_change",
                    severity="medium",
                    title=f"Trend {direction}: {trend.name}",
                    description=f"Change of {change:.1f}% detected.",
                ))

        # Strong increasing risk trend
        if (trend.category.value == "risk" and
            trend.trend_type == TrendType.INCREASING and
            trend.strength == TrendStrength.STRONG):
            alerts.append(self._create_alert(
                trend=trend,
                alert_type="threshold_exceeded",
                severity="high",
                title=f"Rising Risk Trend: {trend.name}",
                description=f"Strong increase of {trend.change_percentage:.1f}% detected.",
            ))

        return alerts

    def _create_alert(
        self,
        trend: Trend,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
    ) -> TrendAlert:
        """Create a trend alert."""
        return TrendAlert(
            tenant_id=trend.tenant_id,
            trend_id=trend.id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
        )

    def _calculate_severity(self, trend: Trend) -> str:
        """Calculate alert severity based on trend."""
        if trend.strength == TrendStrength.STRONG:
            return "high"
        elif trend.strength == TrendStrength.MODERATE:
            return "medium"
        else:
            return "low"

    def set_threshold(self, name: str, value: float) -> None:
        """Set alert threshold."""
        self._thresholds[name] = value

    def clear_history(self) -> None:
        """Clear previous trend history."""
        self._previous_trends.clear()
```

## Test Requirements

### Create `/services/query-service/tests/trends/test_analyzer.py`
```python
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
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/trends/ -v`
2. Verify imports: `python -c "from aswa_query.trends import TrendDetector"`
