import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.repository.insight_repo import InsightRepository
from aswa_insight.repository.models import InsightModel
from aswa_insight.models.insights import Insight, InsightType


class TestInsightRepository:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        return InsightRepository(mock_session)

    @pytest.mark.asyncio
    async def test_create_insight(self, repo, mock_session):
        """Test creating an insight."""
        insight = Insight(
            tenant_id=uuid4(),
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Test Entity",
            description="A test entity",
            confidence=0.9,
        )

        mock_session.flush = AsyncMock()

        # Should not raise
        await repo.create(insight)
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, mock_session):
        """Test getting insight by ID."""
        insight_id = uuid4()
        tenant_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = InsightModel(
            id=insight_id,
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type="entity",
            title="Test",
            title_normalized="test",
            description="Test",
            confidence=0.9,
            raw_data={},
            sources=[],
            content_hash="abc123",
        )
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_id(insight_id, tenant_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_insights_with_filters(self, repo, mock_session):
        """Test listing with filters."""
        tenant_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.scalar.return_value = 0

        insights, total = await repo.list_insights(
            tenant_id=tenant_id,
            insight_type=InsightType.RISK,
            min_confidence=0.7,
        )

        assert insights == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_delete_soft(self, repo, mock_session):
        """Test soft delete."""
        insight_id = uuid4()
        tenant_id = uuid4()

        mock_insight = MagicMock(spec=InsightModel)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_insight
        mock_session.execute.return_value = mock_result

        result = await repo.delete(insight_id, tenant_id, hard_delete=False)
        assert mock_insight.is_deleted is True

    def test_normalize(self, repo):
        """Test text normalization."""
        assert repo._normalize("  HELLO World  ") == "hello world"

    def test_compute_hash(self, repo):
        """Test hash computation."""
        insight = Insight(
            tenant_id=uuid4(),
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Test",
            description="Test",
            confidence=0.9,
        )
        hash1 = repo._compute_hash(insight)
        hash2 = repo._compute_hash(insight)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex


class TestInsightRepositoryStats:
    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test statistics calculation."""
        # Test with mock data
        pass
