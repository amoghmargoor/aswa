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
