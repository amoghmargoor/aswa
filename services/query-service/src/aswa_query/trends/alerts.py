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
