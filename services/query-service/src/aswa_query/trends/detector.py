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
