from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from aswa_insight.repository.models import InsightModel, InsightFeedbackModel
from aswa_insight.scoring.confidence import ConfidenceScorer

logger = structlog.get_logger()


@dataclass
class LearningMetrics:
    """Metrics from feedback learning."""
    tenant_id: UUID
    period_start: datetime
    period_end: datetime

    total_insights: int = 0
    validated_insights: int = 0
    rejected_insights: int = 0
    modified_insights: int = 0

    average_initial_confidence: float = 0.0
    average_final_confidence: float = 0.0
    confidence_calibration_factor: float = 1.0

    by_type: dict[str, dict] = field(default_factory=dict)
    by_category: dict[str, dict] = field(default_factory=dict)

    recommendations: list[str] = field(default_factory=list)


class FeedbackLearner:
    """Learn from user feedback to improve extraction quality."""

    def __init__(
        self,
        session: AsyncSession,
        learning_window_days: int = 30,
        min_feedback_count: int = 10,
    ):
        self.session = session
        self.learning_window_days = learning_window_days
        self.min_feedback_count = min_feedback_count
        self.confidence_scorer = ConfidenceScorer()

    async def compute_learning_metrics(
        self,
        tenant_id: UUID,
        period_days: int | None = None,
    ) -> LearningMetrics:
        """Compute learning metrics from feedback.

        Args:
            tenant_id: Tenant ID
            period_days: Days to analyze (default: learning_window_days)

        Returns:
            LearningMetrics
        """
        days = period_days or self.learning_window_days
        period_start = datetime.utcnow() - timedelta(days=days)
        period_end = datetime.utcnow()

        # Query insights with feedback
        insights_query = (
            select(InsightModel)
            .where(
                InsightModel.tenant_id == tenant_id,
                InsightModel.user_validated == True,
                InsightModel.updated_at >= period_start,
            )
        )
        result = await self.session.execute(insights_query)
        insights = result.scalars().all()

        metrics = LearningMetrics(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            total_insights=len(insights),
        )

        if not insights:
            return metrics

        # Calculate statistics
        confirmed = [i for i in insights if i.validation_status == "confirmed"]
        rejected = [i for i in insights if i.validation_status == "rejected"]
        modified = [i for i in insights if i.validation_status == "modified"]

        metrics.validated_insights = len(confirmed)
        metrics.rejected_insights = len(rejected)
        metrics.modified_insights = len(modified)

        # Confidence analysis
        confidences = [i.confidence for i in insights]
        metrics.average_final_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Calculate calibration factor
        # If many low-confidence insights are confirmed, we're too conservative
        # If many high-confidence insights are rejected, we're too optimistic
        metrics.confidence_calibration_factor = self._calculate_calibration(insights)

        # Breakdown by type
        for insight_type in set(i.insight_type for i in insights):
            type_insights = [i for i in insights if i.insight_type == insight_type]
            type_confirmed = sum(1 for i in type_insights if i.validation_status == "confirmed")
            type_rejected = sum(1 for i in type_insights if i.validation_status == "rejected")

            metrics.by_type[insight_type] = {
                "total": len(type_insights),
                "confirmed": type_confirmed,
                "rejected": type_rejected,
                "accuracy_rate": type_confirmed / max(len(type_insights), 1),
            }

        # Breakdown by category
        for category in set(i.category for i in insights if i.category):
            cat_insights = [i for i in insights if i.category == category]
            cat_confirmed = sum(1 for i in cat_insights if i.validation_status == "confirmed")
            cat_rejected = sum(1 for i in cat_insights if i.validation_status == "rejected")

            metrics.by_category[category] = {
                "total": len(cat_insights),
                "confirmed": cat_confirmed,
                "rejected": cat_rejected,
                "accuracy_rate": cat_confirmed / max(len(cat_insights), 1),
            }

        # Generate recommendations
        metrics.recommendations = self._generate_recommendations(metrics)

        return metrics

    async def get_calibration_factor(
        self,
        tenant_id: UUID,
        insight_type: str | None = None,
    ) -> float:
        """Get confidence calibration factor.

        Returns a factor to apply to raw confidence scores based on feedback.

        Args:
            tenant_id: Tenant ID
            insight_type: Optional insight type filter

        Returns:
            Calibration factor (1.0 = no change)
        """
        metrics = await self.compute_learning_metrics(tenant_id)

        if insight_type and insight_type in metrics.by_type:
            type_metrics = metrics.by_type[insight_type]
            accuracy_rate = type_metrics.get("accuracy_rate", 0.5)

            # Adjust calibration based on accuracy
            if accuracy_rate > 0.8:
                return 1.1  # Slightly boost confidence
            elif accuracy_rate < 0.5:
                return 0.8  # Reduce confidence
            else:
                return 1.0

        return metrics.confidence_calibration_factor

    async def identify_problem_patterns(
        self,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Identify patterns in rejected insights.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of problem pattern descriptions
        """
        # Query rejected insights
        query = select(InsightModel).where(
            InsightModel.tenant_id == tenant_id,
            InsightModel.validation_status == "rejected",
        ).limit(100)

        result = await self.session.execute(query)
        rejected = result.scalars().all()

        if not rejected:
            return []

        patterns = []

        # Analyze by category
        categories = {}
        for insight in rejected:
            cat = insight.category or "uncategorized"
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        for cat, count in categories.items():
            if count >= 3:
                patterns.append({
                    "pattern_type": "high_rejection_category",
                    "category": cat,
                    "rejection_count": count,
                    "suggestion": f"Review extraction rules for category '{cat}'",
                })

        # Analyze by confidence level
        low_conf_rejected = [i for i in rejected if i.confidence < 0.5]
        high_conf_rejected = [i for i in rejected if i.confidence >= 0.8]

        if high_conf_rejected:
            patterns.append({
                "pattern_type": "overconfident_rejections",
                "count": len(high_conf_rejected),
                "suggestion": "High-confidence insights are being rejected; calibrate confidence scoring",
            })

        return patterns

    def _calculate_calibration(self, insights: list[InsightModel]) -> float:
        """Calculate calibration factor from feedback."""
        if not insights:
            return 1.0

        # Group by confidence levels
        high_conf = [i for i in insights if i.confidence >= 0.8]
        low_conf = [i for i in insights if i.confidence < 0.5]

        high_conf_accuracy = (
            sum(1 for i in high_conf if i.validation_status == "confirmed")
            / max(len(high_conf), 1)
        )
        low_conf_accuracy = (
            sum(1 for i in low_conf if i.validation_status == "confirmed")
            / max(len(low_conf), 1)
        )

        # If high-confidence insights have low accuracy, we're overconfident
        if high_conf_accuracy < 0.7 and len(high_conf) >= 5:
            return 0.9  # Reduce all confidences
        # If low-confidence insights have high accuracy, we're too conservative
        elif low_conf_accuracy > 0.7 and len(low_conf) >= 5:
            return 1.1  # Boost all confidences

        return 1.0

    def _generate_recommendations(self, metrics: LearningMetrics) -> list[str]:
        """Generate recommendations based on metrics."""
        recommendations = []

        validation_rate = metrics.validated_insights / max(metrics.total_insights, 1)
        rejection_rate = metrics.rejected_insights / max(metrics.total_insights, 1)

        if rejection_rate > 0.3:
            recommendations.append(
                "High rejection rate detected. Consider reviewing extraction prompts."
            )

        if metrics.confidence_calibration_factor < 0.95:
            recommendations.append(
                "Confidence scores appear overconfident. Apply calibration to reduce scores."
            )
        elif metrics.confidence_calibration_factor > 1.05:
            recommendations.append(
                "Confidence scores appear conservative. Consider boosting scores."
            )

        # Type-specific recommendations
        for insight_type, type_metrics in metrics.by_type.items():
            if type_metrics.get("accuracy_rate", 1.0) < 0.5:
                recommendations.append(
                    f"Low accuracy for {insight_type} insights. Review {insight_type} extraction prompts."
                )

        return recommendations
