# Task 3.4.3: Insight Feedback Loop (User Corrections)

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The repository layer is at `/services/insight-engine/src/aswa_insight/repository/` with insight and feedback models already defined.

Users need to provide feedback on extracted insights to improve quality and correct errors. This feedback should:
1. Allow rating and validation of insights
2. Support corrections to insight data
3. Influence future extraction confidence
4. Track feedback history for analysis

## Objective

Create a feedback system that:
1. Collects user feedback on insights (ratings, accuracy, corrections)
2. Applies corrections to insights
3. Uses feedback to adjust confidence scores
4. Provides feedback analytics

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/feedback/__init__.py`
```python
from .models import FeedbackRequest, FeedbackResponse, FeedbackType, CorrectionRequest
from .service import FeedbackService
from .learning import FeedbackLearner, LearningMetrics
from .analytics import FeedbackAnalytics

__all__ = [
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackType",
    "CorrectionRequest",
    "FeedbackService",
    "FeedbackLearner",
    "LearningMetrics",
    "FeedbackAnalytics",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/feedback/models.py`
Feedback data models:

```python
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Types of feedback."""
    RATING = "rating"
    ACCURACY = "accuracy"
    CORRECTION = "correction"
    FLAG = "flag"
    DISMISS = "dismiss"


class ValidationStatus(str, Enum):
    """Validation status after feedback."""
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    MODIFIED = "modified"
    PENDING = "pending"


class FeedbackRequest(BaseModel):
    """Request to submit feedback on an insight."""
    insight_id: UUID
    feedback_type: FeedbackType
    rating: int | None = Field(None, ge=1, le=5, description="Rating 1-5")
    is_accurate: bool | None = Field(None, description="Is the insight accurate?")
    comment: str | None = Field(None, max_length=2000, description="Optional comment")
    flag_reason: str | None = Field(None, max_length=500, description="Reason for flagging")


class CorrectionRequest(BaseModel):
    """Request to correct an insight."""
    insight_id: UUID
    corrections: dict[str, Any] = Field(..., description="Fields to correct")
    correction_reason: str = Field(..., max_length=500, description="Reason for correction")

    # Correctable fields
    title: str | None = None
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    impact: str | None = None
    confidence_override: float | None = Field(None, ge=0, le=1)


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    id: UUID = Field(default_factory=uuid4)
    insight_id: UUID
    feedback_type: FeedbackType
    applied: bool = True
    previous_confidence: float | None = None
    new_confidence: float | None = None
    validation_status: ValidationStatus | None = None
    message: str = ""


class FeedbackSummary(BaseModel):
    """Summary of feedback for an insight."""
    insight_id: UUID
    total_feedback_count: int = 0
    average_rating: float | None = None
    positive_accuracy_count: int = 0
    negative_accuracy_count: int = 0
    correction_count: int = 0
    flag_count: int = 0
    validation_status: ValidationStatus = ValidationStatus.PENDING
    confidence_adjustment: float = 0.0
    last_feedback_at: datetime | None = None


class UserFeedbackHistory(BaseModel):
    """Feedback history for a user."""
    user_id: UUID
    total_feedback_given: int = 0
    insights_confirmed: int = 0
    insights_rejected: int = 0
    corrections_made: int = 0
    average_agreement_rate: float = 0.0
```

### 3. Create `/services/insight-engine/src/aswa_insight/feedback/service.py`
Feedback service:

```python
from datetime import datetime
from typing import Any
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from aswa_insight.repository.models import InsightModel, InsightFeedbackModel
from aswa_insight.repository.insight_repo import InsightRepository
from aswa_insight.scoring.confidence import ConfidenceAdjuster, ConfidenceAdjustment, AdjustmentReason

from .models import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackType,
    CorrectionRequest,
    FeedbackSummary,
    ValidationStatus,
)

logger = structlog.get_logger()


class FeedbackService:
    """Service for handling user feedback on insights."""

    def __init__(
        self,
        session: AsyncSession,
        confidence_adjuster: ConfidenceAdjuster | None = None,
    ):
        self.session = session
        self.repository = InsightRepository(session)
        self.confidence_adjuster = confidence_adjuster or ConfidenceAdjuster()

    async def submit_feedback(
        self,
        tenant_id: UUID,
        user_id: UUID,
        request: FeedbackRequest,
    ) -> FeedbackResponse:
        """Submit feedback on an insight.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            request: Feedback request

        Returns:
            FeedbackResponse
        """
        # Get the insight
        insight = await self.repository.get_by_id(request.insight_id, tenant_id)
        if not insight:
            return FeedbackResponse(
                insight_id=request.insight_id,
                feedback_type=request.feedback_type,
                applied=False,
                message="Insight not found",
            )

        previous_confidence = insight.confidence

        # Check for existing feedback from this user
        existing = await self._get_user_feedback(request.insight_id, user_id)

        if existing:
            # Update existing feedback
            feedback = await self._update_feedback(existing, request)
        else:
            # Create new feedback
            feedback = await self._create_feedback(
                insight_id=request.insight_id,
                tenant_id=tenant_id,
                user_id=user_id,
                request=request,
            )

        # Process feedback effects
        new_confidence, validation_status = await self._process_feedback(
            insight=insight,
            feedback=feedback,
            request=request,
        )

        await self.session.commit()

        logger.info(
            "Feedback submitted",
            insight_id=str(request.insight_id),
            user_id=str(user_id),
            feedback_type=request.feedback_type,
            validation_status=validation_status,
        )

        return FeedbackResponse(
            insight_id=request.insight_id,
            feedback_type=request.feedback_type,
            applied=True,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            validation_status=validation_status,
            message="Feedback recorded successfully",
        )

    async def submit_correction(
        self,
        tenant_id: UUID,
        user_id: UUID,
        request: CorrectionRequest,
    ) -> FeedbackResponse:
        """Submit a correction to an insight.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
            request: Correction request

        Returns:
            FeedbackResponse
        """
        insight = await self.repository.get_by_id(request.insight_id, tenant_id)
        if not insight:
            return FeedbackResponse(
                insight_id=request.insight_id,
                feedback_type=FeedbackType.CORRECTION,
                applied=False,
                message="Insight not found",
            )

        previous_confidence = insight.confidence

        # Build updates from correction
        updates = {}
        if request.title:
            updates["title"] = request.title
        if request.description:
            updates["description"] = request.description
        if request.category:
            updates["category"] = request.category
        if request.severity:
            updates["severity"] = request.severity
        if request.impact:
            updates["impact"] = request.impact
        if request.confidence_override is not None:
            updates["confidence"] = request.confidence_override

        # Apply updates
        if updates:
            await self.repository.update(
                insight_id=request.insight_id,
                tenant_id=tenant_id,
                updates=updates,
            )

        # Record the correction as feedback
        feedback = InsightFeedbackModel(
            insight_id=request.insight_id,
            tenant_id=tenant_id,
            user_id=user_id,
            comment=request.correction_reason,
            correction=request.corrections,
        )
        self.session.add(feedback)

        # Update validation status
        insight.user_validated = True
        insight.validation_status = ValidationStatus.MODIFIED.value

        await self.session.commit()

        logger.info(
            "Correction submitted",
            insight_id=str(request.insight_id),
            user_id=str(user_id),
            fields_corrected=list(updates.keys()),
        )

        return FeedbackResponse(
            insight_id=request.insight_id,
            feedback_type=FeedbackType.CORRECTION,
            applied=True,
            previous_confidence=previous_confidence,
            new_confidence=insight.confidence,
            validation_status=ValidationStatus.MODIFIED,
            message=f"Correction applied to fields: {', '.join(updates.keys())}",
        )

    async def get_feedback_summary(
        self,
        insight_id: UUID,
        tenant_id: UUID,
    ) -> FeedbackSummary | None:
        """Get feedback summary for an insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID

        Returns:
            FeedbackSummary or None
        """
        # Query feedback
        query = select(InsightFeedbackModel).where(
            InsightFeedbackModel.insight_id == insight_id,
            InsightFeedbackModel.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        feedbacks = result.scalars().all()

        if not feedbacks:
            return FeedbackSummary(insight_id=insight_id)

        # Calculate statistics
        ratings = [f.rating for f in feedbacks if f.rating is not None]
        accuracy_positive = sum(1 for f in feedbacks if f.is_accurate is True)
        accuracy_negative = sum(1 for f in feedbacks if f.is_accurate is False)
        corrections = sum(1 for f in feedbacks if f.correction is not None)

        # Get insight validation status
        insight = await self.repository.get_by_id(insight_id, tenant_id)
        validation_status = ValidationStatus.PENDING
        if insight and insight.validation_status:
            validation_status = ValidationStatus(insight.validation_status)

        return FeedbackSummary(
            insight_id=insight_id,
            total_feedback_count=len(feedbacks),
            average_rating=sum(ratings) / len(ratings) if ratings else None,
            positive_accuracy_count=accuracy_positive,
            negative_accuracy_count=accuracy_negative,
            correction_count=corrections,
            validation_status=validation_status,
            last_feedback_at=max(f.created_at for f in feedbacks) if feedbacks else None,
        )

    async def get_user_feedback_history(
        self,
        user_id: UUID,
        tenant_id: UUID,
        limit: int = 100,
    ) -> list[InsightFeedbackModel]:
        """Get feedback history for a user.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            limit: Max results

        Returns:
            List of feedback records
        """
        query = (
            select(InsightFeedbackModel)
            .where(
                InsightFeedbackModel.user_id == user_id,
                InsightFeedbackModel.tenant_id == tenant_id,
            )
            .order_by(InsightFeedbackModel.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _get_user_feedback(
        self,
        insight_id: UUID,
        user_id: UUID,
    ) -> InsightFeedbackModel | None:
        """Get existing feedback from user."""
        query = select(InsightFeedbackModel).where(
            InsightFeedbackModel.insight_id == insight_id,
            InsightFeedbackModel.user_id == user_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _create_feedback(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        request: FeedbackRequest,
    ) -> InsightFeedbackModel:
        """Create new feedback record."""
        feedback = InsightFeedbackModel(
            insight_id=insight_id,
            tenant_id=tenant_id,
            user_id=user_id,
            rating=request.rating,
            is_accurate=request.is_accurate,
            comment=request.comment,
        )
        self.session.add(feedback)
        await self.session.flush()
        return feedback

    async def _update_feedback(
        self,
        existing: InsightFeedbackModel,
        request: FeedbackRequest,
    ) -> InsightFeedbackModel:
        """Update existing feedback."""
        if request.rating is not None:
            existing.rating = request.rating
        if request.is_accurate is not None:
            existing.is_accurate = request.is_accurate
        if request.comment:
            existing.comment = request.comment

        await self.session.flush()
        return existing

    async def _process_feedback(
        self,
        insight: InsightModel,
        feedback: InsightFeedbackModel,
        request: FeedbackRequest,
    ) -> tuple[float, ValidationStatus]:
        """Process feedback and update insight.

        Returns:
            Tuple of (new_confidence, validation_status)
        """
        validation_status = ValidationStatus.PENDING

        if request.feedback_type == FeedbackType.ACCURACY:
            if request.is_accurate is True:
                validation_status = ValidationStatus.CONFIRMED
                insight.user_validated = True
                insight.validation_status = validation_status.value

                # Boost confidence slightly
                adjustment = ConfidenceAdjustment(
                    reason=AdjustmentReason.USER_FEEDBACK,
                    factor=1.05,  # 5% boost
                    description="User confirmed accuracy",
                )
                insight.confidence, _ = self.confidence_adjuster.adjust(
                    insight.confidence, [adjustment]
                )

            elif request.is_accurate is False:
                validation_status = ValidationStatus.REJECTED
                insight.user_validated = True
                insight.validation_status = validation_status.value

                # Reduce confidence
                adjustment = ConfidenceAdjustment(
                    reason=AdjustmentReason.USER_FEEDBACK,
                    factor=0.7,  # 30% reduction
                    description="User rejected accuracy",
                )
                insight.confidence, _ = self.confidence_adjuster.adjust(
                    insight.confidence, [adjustment]
                )

        elif request.feedback_type == FeedbackType.DISMISS:
            insight.is_deleted = True
            insight.deleted_at = datetime.utcnow()
            validation_status = ValidationStatus.REJECTED

        await self.session.flush()
        return insight.confidence, validation_status
```

### 4. Create `/services/insight-engine/src/aswa_insight/feedback/learning.py`
Feedback-based learning:

```python
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
```

### 5. Create `/services/insight-engine/src/aswa_insight/feedback/analytics.py`
Feedback analytics:

```python
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
```

## Test Requirements

### Create `/services/insight-engine/tests/feedback/__init__.py`

### Create `/services/insight-engine/tests/feedback/test_models.py`
```python
import pytest
from uuid import uuid4

from aswa_insight.feedback.models import (
    FeedbackRequest,
    FeedbackType,
    CorrectionRequest,
    FeedbackSummary,
)


class TestFeedbackRequest:
    def test_valid_rating_feedback(self):
        """Test valid rating feedback."""
        request = FeedbackRequest(
            insight_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=4,
        )
        assert request.rating == 4

    def test_rating_bounds(self):
        """Test rating must be 1-5."""
        with pytest.raises(ValueError):
            FeedbackRequest(
                insight_id=uuid4(),
                feedback_type=FeedbackType.RATING,
                rating=6,
            )

    def test_accuracy_feedback(self):
        """Test accuracy feedback."""
        request = FeedbackRequest(
            insight_id=uuid4(),
            feedback_type=FeedbackType.ACCURACY,
            is_accurate=True,
            comment="Looks correct",
        )
        assert request.is_accurate is True


class TestCorrectionRequest:
    def test_valid_correction(self):
        """Test valid correction request."""
        request = CorrectionRequest(
            insight_id=uuid4(),
            corrections={"title": "Fixed Title"},
            correction_reason="Title was incorrect",
            title="Fixed Title",
        )
        assert request.title == "Fixed Title"

    def test_confidence_override_bounds(self):
        """Test confidence override must be 0-1."""
        with pytest.raises(ValueError):
            CorrectionRequest(
                insight_id=uuid4(),
                corrections={},
                correction_reason="Test",
                confidence_override=1.5,
            )
```

### Create `/services/insight-engine/tests/feedback/test_service.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.feedback.service import FeedbackService
from aswa_insight.feedback.models import FeedbackRequest, FeedbackType, ValidationStatus
from aswa_insight.repository.models import InsightModel


class TestFeedbackService:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return FeedbackService(mock_session)

    @pytest.mark.asyncio
    async def test_submit_feedback_insight_not_found(self, service):
        """Test feedback for non-existent insight."""
        request = FeedbackRequest(
            insight_id=uuid4(),
            feedback_type=FeedbackType.RATING,
            rating=5,
        )

        # Mock repository to return None
        service.repository.get_by_id = AsyncMock(return_value=None)

        response = await service.submit_feedback(
            tenant_id=uuid4(),
            user_id=uuid4(),
            request=request,
        )

        assert response.applied is False
        assert "not found" in response.message

    @pytest.mark.asyncio
    async def test_submit_accuracy_positive(self, service, mock_session):
        """Test positive accuracy feedback."""
        insight_id = uuid4()
        insight = MagicMock(spec=InsightModel)
        insight.id = insight_id
        insight.confidence = 0.7
        insight.user_validated = False

        service.repository.get_by_id = AsyncMock(return_value=insight)
        service._get_user_feedback = AsyncMock(return_value=None)

        request = FeedbackRequest(
            insight_id=insight_id,
            feedback_type=FeedbackType.ACCURACY,
            is_accurate=True,
        )

        response = await service.submit_feedback(
            tenant_id=uuid4(),
            user_id=uuid4(),
            request=request,
        )

        assert response.applied is True
        assert response.validation_status == ValidationStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_submit_accuracy_negative(self, service, mock_session):
        """Test negative accuracy feedback."""
        insight_id = uuid4()
        insight = MagicMock(spec=InsightModel)
        insight.id = insight_id
        insight.confidence = 0.8

        service.repository.get_by_id = AsyncMock(return_value=insight)
        service._get_user_feedback = AsyncMock(return_value=None)

        request = FeedbackRequest(
            insight_id=insight_id,
            feedback_type=FeedbackType.ACCURACY,
            is_accurate=False,
        )

        response = await service.submit_feedback(
            tenant_id=uuid4(),
            user_id=uuid4(),
            request=request,
        )

        assert response.applied is True
        assert response.validation_status == ValidationStatus.REJECTED
        assert response.new_confidence < response.previous_confidence


class TestFeedbackSummary:
    @pytest.mark.asyncio
    async def test_get_feedback_summary(self, mock_session):
        """Test getting feedback summary."""
        service = FeedbackService(mock_session)

        # Mock empty feedback
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        summary = await service.get_feedback_summary(
            insight_id=uuid4(),
            tenant_id=uuid4(),
        )

        assert summary is not None
        assert summary.total_feedback_count == 0
```

### Create `/services/insight-engine/tests/feedback/test_learning.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.feedback.learning import FeedbackLearner, LearningMetrics


class TestFeedbackLearner:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def learner(self, mock_session):
        return FeedbackLearner(mock_session)

    @pytest.mark.asyncio
    async def test_compute_learning_metrics_empty(self, learner, mock_session):
        """Test metrics with no feedback."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        metrics = await learner.compute_learning_metrics(uuid4())

        assert metrics.total_insights == 0
        assert metrics.confidence_calibration_factor == 1.0

    @pytest.mark.asyncio
    async def test_calibration_factor(self, learner):
        """Test calibration factor calculation."""
        # Default calibration should be 1.0
        factor = await learner.get_calibration_factor(uuid4())
        assert 0.5 <= factor <= 1.5


class TestLearningMetrics:
    def test_learning_metrics_creation(self):
        """Test creating learning metrics."""
        from datetime import datetime

        metrics = LearningMetrics(
            tenant_id=uuid4(),
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            total_insights=100,
            validated_insights=80,
            rejected_insights=20,
        )

        assert metrics.total_insights == 100
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/feedback/ -v`
2. Verify imports: `python -c "from aswa_insight.feedback import *"`
3. Test feedback flow end-to-end with mock data
