import pytest
from uuid import uuid4

from aswa_insight.repository.deduplication import (
    DuplicateDetector,
    DeduplicationService,
    DuplicateMatch,
)
from aswa_insight.models.insights import Insight, InsightType


class TestDuplicateDetector:
    @pytest.fixture
    def detector(self):
        return DuplicateDetector(similarity_threshold=0.85)

    def test_compute_hash_consistent(self, detector):
        """Test hash is consistent."""
        insight = Insight(
            tenant_id=uuid4(),
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Test Entity",
            description="Description",
            confidence=0.9,
        )
        hash1 = detector.compute_hash(insight)
        hash2 = detector.compute_hash(insight)
        assert hash1 == hash2

    def test_compute_hash_different_for_different_titles(self, detector):
        """Test different titles produce different hashes."""
        tenant_id = uuid4()
        insight1 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Entity One",
            description="Description",
            confidence=0.9,
        )
        insight2 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Entity Two",
            description="Description",
            confidence=0.9,
        )
        assert detector.compute_hash(insight1) != detector.compute_hash(insight2)

    def test_compute_similarity_identical(self, detector):
        """Test identical insights have similarity 1.0."""
        insight = Insight(
            tenant_id=uuid4(),
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Test Entity",
            description="Description",
            confidence=0.9,
        )
        assert detector.compute_similarity(insight, insight) == 1.0

    def test_compute_similarity_different_type(self, detector):
        """Test different types have similarity 0."""
        tenant_id = uuid4()
        insight1 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Test",
            description="Description",
            confidence=0.9,
        )
        insight2 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.RISK,
            title="Test",
            description="Description",
            confidence=0.9,
        )
        assert detector.compute_similarity(insight1, insight2) == 0.0

    def test_compute_similarity_partial_match(self, detector):
        """Test partial title match."""
        tenant_id = uuid4()
        insight1 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Acme Corporation",
            description="Description",
            confidence=0.9,
        )
        insight2 = Insight(
            tenant_id=tenant_id,
            document_id=uuid4(),
            insight_type=InsightType.ENTITY,
            title="Acme Corp",
            description="Description",
            confidence=0.9,
        )
        similarity = detector.compute_similarity(insight1, insight2)
        assert 0 < similarity < 1


class TestDeduplicationService:
    @pytest.mark.asyncio
    async def test_check_and_store_new(self):
        """Test storing new insight (no duplicate)."""
        # Requires mock session setup
        pass

    @pytest.mark.asyncio
    async def test_check_and_store_exact_duplicate(self):
        """Test detecting exact duplicate."""
        pass

    @pytest.mark.asyncio
    async def test_deduplicate_batch(self):
        """Test batch deduplication."""
        pass
