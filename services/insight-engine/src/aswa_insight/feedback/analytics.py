from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from aswa_insight.repository.models import InsightModel, InsightFeedbackModel

logger = structlog.get_logger()


@dataclass
class FeedbackTrend:
    """Trend data for feedback analytics."""
    date: datetime
    feedback_count: int
    positive_count: int
    negative_count: int
    average_rating: float | None


@dataclass
class UserAnalytics:
    """Analytics for user feedback behavior."""
    user_id: UUID
    total_feedback: int
    confirmations: int
    rejections: int
    corrections: int
    average_rating_given: float | None
    agreement_rate: float  # How often user agrees with majority


class FeedbackAnalytics:
    """Analytics for feedback data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_feedback_trends(
        self,
        tenant_id: UUID,
        days: int = 30,
        granularity: str = "day",
    ) -> list[FeedbackTrend]:
        """Get feedback trends over time.

        Args:
            tenant_id: Tenant ID
            days: Number of days to analyze
            granularity: "day" or "week"

        Returns:
            List of FeedbackTrend
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Query feedback grouped by date
        if granularity == "day":
            date_trunc = func.date_trunc("day", InsightFeedbackModel.created_at)
        else:
            date_trunc = func.date_trunc("week", InsightFeedbackModel.created_at)

        query = (
            select(
                date_trunc.label("period"),
                func.count().label("total"),
                func.count().filter(InsightFeedbackModel.is_accurate == True).label("positive"),
                func.count().filter(InsightFeedbackModel.is_accurate == False).label("negative"),
                func.avg(InsightFeedbackModel.rating).label("avg_rating"),
            )
            .where(
                InsightFeedbackModel.tenant_id == tenant_id,
                InsightFeedbackModel.created_at >= start_date,
            )
            .group_by("period")
            .order_by("period")
        )

        result = await self.session.execute(query)
        rows = result.all()

        trends = []
        for row in rows:
            trends.append(FeedbackTrend(
                date=row.period,
                feedback_count=row.total,
                positive_count=row.positive or 0,
                negative_count=row.negative or 0,
                average_rating=float(row.avg_rating) if row.avg_rating else None,
            ))

        return trends

    async def get_user_analytics(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> UserAnalytics:
        """Get analytics for a specific user.

        Args:
            tenant_id: Tenant ID
            user_id: User ID

        Returns:
            UserAnalytics
        """
        query = select(InsightFeedbackModel).where(
            InsightFeedbackModel.tenant_id == tenant_id,
            InsightFeedbackModel.user_id == user_id,
        )

        result = await self.session.execute(query)
        feedbacks = result.scalars().all()

        if not feedbacks:
            return UserAnalytics(
                user_id=user_id,
                total_feedback=0,
                confirmations=0,
                rejections=0,
                corrections=0,
                average_rating_given=None,
                agreement_rate=0.0,
            )

        confirmations = sum(1 for f in feedbacks if f.is_accurate is True)
        rejections = sum(1 for f in feedbacks if f.is_accurate is False)
        corrections = sum(1 for f in feedbacks if f.correction is not None)
        ratings = [f.rating for f in feedbacks if f.rating is not None]

        return UserAnalytics(
            user_id=user_id,
            total_feedback=len(feedbacks),
            confirmations=confirmations,
            rejections=rejections,
            corrections=corrections,
            average_rating_given=sum(ratings) / len(ratings) if ratings else None,
            agreement_rate=await self._calculate_agreement_rate(feedbacks),
        )

    async def get_top_contributors(
        self,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get top feedback contributors.

        Args:
            tenant_id: Tenant ID
            limit: Maximum contributors to return

        Returns:
            List of contributor info
        """
        query = (
            select(
                InsightFeedbackModel.user_id,
                func.count().label("feedback_count"),
                func.avg(InsightFeedbackModel.rating).label("avg_rating"),
            )
            .where(InsightFeedbackModel.tenant_id == tenant_id)
            .group_by(InsightFeedbackModel.user_id)
            .order_by(func.count().desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "user_id": str(row.user_id),
                "feedback_count": row.feedback_count,
                "average_rating": float(row.avg_rating) if row.avg_rating else None,
            }
            for row in rows
        ]

    async def get_insight_quality_metrics(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Get overall insight quality metrics.

        Args:
            tenant_id: Tenant ID

        Returns:
            Quality metrics dictionary
        """
        # Get insights with feedback
        insights_query = select(InsightModel).where(
            InsightModel.tenant_id == tenant_id,
            InsightModel.user_validated == True,
        )
        result = await self.session.execute(insights_query)
        insights = result.scalars().all()

        if not insights:
            return {
                "total_validated": 0,
                "accuracy_rate": None,
                "average_confidence": None,
            }

        confirmed = sum(1 for i in insights if i.validation_status == "confirmed")
        rejected = sum(1 for i in insights if i.validation_status == "rejected")
        modified = sum(1 for i in insights if i.validation_status == "modified")

        confidences = [i.confidence for i in insights]

        return {
            "total_validated": len(insights),
            "confirmed_count": confirmed,
            "rejected_count": rejected,
            "modified_count": modified,
            "accuracy_rate": confirmed / len(insights) if insights else None,
            "average_confidence": sum(confidences) / len(confidences) if confidences else None,
            "by_type": self._group_by_type(insights),
        }

    async def _calculate_agreement_rate(
        self,
        feedbacks: list[InsightFeedbackModel],
    ) -> float:
        """Calculate how often user agrees with majority."""
        if not feedbacks:
            return 0.0

        agreements = 0
        for feedback in feedbacks:
            # Get other feedback on same insight
            other_query = select(InsightFeedbackModel).where(
                InsightFeedbackModel.insight_id == feedback.insight_id,
                InsightFeedbackModel.id != feedback.id,
            )
            result = await self.session.execute(other_query)
            others = result.scalars().all()

            if not others:
                continue

            # Check if user's accuracy vote matches majority
            if feedback.is_accurate is not None:
                positive_count = sum(1 for o in others if o.is_accurate is True)
                negative_count = sum(1 for o in others if o.is_accurate is False)

                majority_positive = positive_count > negative_count

                if (feedback.is_accurate and majority_positive) or \
                   (not feedback.is_accurate and not majority_positive):
                    agreements += 1

        return agreements / len(feedbacks) if feedbacks else 0.0

    def _group_by_type(self, insights: list[InsightModel]) -> dict[str, dict]:
        """Group insights by type."""
        by_type = {}
        for insight in insights:
            itype = insight.insight_type
            if itype not in by_type:
                by_type[itype] = {"total": 0, "confirmed": 0, "rejected": 0}

            by_type[itype]["total"] += 1
            if insight.validation_status == "confirmed":
                by_type[itype]["confirmed"] += 1
            elif insight.validation_status == "rejected":
                by_type[itype]["rejected"] += 1

        return by_type
