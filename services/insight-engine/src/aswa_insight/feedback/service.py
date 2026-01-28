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
