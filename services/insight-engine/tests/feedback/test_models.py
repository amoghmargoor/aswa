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
