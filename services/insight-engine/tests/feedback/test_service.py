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
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

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
