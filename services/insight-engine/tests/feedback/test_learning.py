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
    async def test_calibration_factor(self, learner, mock_session):
        """Test calibration factor calculation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

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
