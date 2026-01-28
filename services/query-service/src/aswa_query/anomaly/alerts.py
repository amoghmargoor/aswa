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
