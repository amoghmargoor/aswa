# Task 3.4.1: Insight Repository & Deduplication

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The extraction pipeline is complete and produces `Insight` objects from `/services/insight-engine/src/aswa_insight/models/insights.py`.

The database infrastructure uses SQLAlchemy with async PostgreSQL, following patterns from the ingestion service at `/services/ingestion-service/`.

## Objective

Create a repository layer for persisting and querying insights with:
1. CRUD operations for insights
2. Deduplication logic to prevent duplicate insights
3. Search and filtering capabilities
4. Tenant isolation

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/repository/__init__.py`
```python
from .models import InsightModel, EntityModel, InsightFeedbackModel
from .insight_repo import InsightRepository
from .deduplication import DeduplicationService, DuplicateDetector

__all__ = [
    "InsightModel",
    "EntityModel",
    "InsightFeedbackModel",
    "InsightRepository",
    "DeduplicationService",
    "DuplicateDetector",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/repository/models.py`
SQLAlchemy models for database:

```python
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from aswa_insight.models.insights import InsightType
from aswa_insight.models.risks import Severity
from aswa_insight.models.opportunities import ImpactLevel


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class InsightModel(Base):
    """SQLAlchemy model for insights."""

    __tablename__ = "insights"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    insight_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Type-specific fields
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Raw extraction data
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Deduplication
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_duplicate_of: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=True)
    merge_count: Mapped[int] = mapped_column(default=1)

    # Validation
    user_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # confirmed, rejected, modified

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    feedback: Mapped[list["InsightFeedbackModel"]] = relationship(back_populates="insight")
    related_entities: Mapped[list["InsightEntityModel"]] = relationship(back_populates="insight")

    __table_args__ = (
        Index("ix_insights_tenant_type", "tenant_id", "insight_type"),
        Index("ix_insights_tenant_document", "tenant_id", "document_id"),
        Index("ix_insights_tenant_hash", "tenant_id", "content_hash"),
        Index("ix_insights_confidence", "confidence"),
    )


class EntityModel(Base):
    """SQLAlchemy model for extracted entities."""

    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Aggregated confidence (from multiple extractions)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    mention_count: Mapped[int] = mapped_column(default=1)

    # Canonical entity reference (for deduplication)
    canonical_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_entities_tenant_name", "tenant_id", "name_normalized"),
        UniqueConstraint("tenant_id", "name_normalized", "entity_type", name="uq_entity_tenant_name_type"),
    )


class InsightEntityModel(Base):
    """Junction table linking insights to entities."""

    __tablename__ = "insight_entities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    insight: Mapped["InsightModel"] = relationship(back_populates="related_entities")

    __table_args__ = (
        UniqueConstraint("insight_id", "entity_id", name="uq_insight_entity"),
    )


class InsightFeedbackModel(Base):
    """User feedback on insights."""

    __tablename__ = "insight_feedback"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    rating: Mapped[int | None] = mapped_column(nullable=True)  # 1-5
    is_accurate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    insight: Mapped["InsightModel"] = relationship(back_populates="feedback")

    __table_args__ = (
        Index("ix_feedback_insight", "insight_id"),
        UniqueConstraint("insight_id", "user_id", name="uq_feedback_insight_user"),
    )
```

### 3. Create `/services/insight-engine/src/aswa_insight/repository/insight_repo.py`
Insight repository with CRUD operations:

```python
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID
import hashlib

from sqlalchemy import select, func, and_, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from .models import InsightModel, InsightFeedbackModel, InsightEntityModel
from aswa_insight.models.insights import Insight, InsightType

logger = structlog.get_logger()


class InsightRepository:
    """Repository for insight persistence and queries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, insight: Insight) -> InsightModel:
        """Create a new insight.

        Args:
            insight: Insight to create

        Returns:
            Created InsightModel
        """
        content_hash = self._compute_hash(insight)

        model = InsightModel(
            id=insight.id,
            tenant_id=insight.tenant_id,
            document_id=insight.document_id,
            insight_type=insight.insight_type.value,
            title=insight.title,
            title_normalized=self._normalize(insight.title),
            description=insight.description,
            confidence=insight.confidence,
            category=insight.category,
            severity=insight.severity.value if insight.severity else None,
            impact=insight.impact.value if insight.impact else None,
            raw_data=insight.raw_data,
            sources=[s.model_dump() for s in insight.sources] if insight.sources else [],
            content_hash=content_hash,
            user_validated=insight.user_validated,
        )

        self.session.add(model)
        await self.session.flush()

        logger.info(
            "Insight created",
            insight_id=str(model.id),
            tenant_id=str(model.tenant_id),
            type=model.insight_type,
        )

        return model

    async def create_many(self, insights: list[Insight]) -> list[InsightModel]:
        """Create multiple insights.

        Args:
            insights: List of insights to create

        Returns:
            List of created InsightModels
        """
        models = []
        for insight in insights:
            model = await self.create(insight)
            models.append(model)

        return models

    async def get_by_id(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        include_deleted: bool = False,
    ) -> InsightModel | None:
        """Get insight by ID.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID (for isolation)
            include_deleted: Include soft-deleted insights

        Returns:
            InsightModel or None
        """
        query = select(InsightModel).where(
            InsightModel.id == insight_id,
            InsightModel.tenant_id == tenant_id,
        )

        if not include_deleted:
            query = query.where(InsightModel.is_deleted == False)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_insights(
        self,
        tenant_id: UUID,
        document_id: UUID | None = None,
        insight_type: InsightType | None = None,
        category: str | None = None,
        min_confidence: float | None = None,
        user_validated: bool | None = None,
        search_query: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> tuple[Sequence[InsightModel], int]:
        """List insights with filters.

        Args:
            tenant_id: Tenant ID
            document_id: Optional document filter
            insight_type: Optional type filter
            category: Optional category filter
            min_confidence: Minimum confidence threshold
            user_validated: Filter by validation status
            search_query: Text search in title/description
            limit: Max results
            offset: Offset for pagination
            order_by: Field to order by
            order_desc: Descending order

        Returns:
            Tuple of (insights, total_count)
        """
        # Base query
        query = select(InsightModel).where(
            InsightModel.tenant_id == tenant_id,
            InsightModel.is_deleted == False,
            InsightModel.is_duplicate_of == None,  # Only show canonical insights
        )

        # Apply filters
        if document_id:
            query = query.where(InsightModel.document_id == document_id)

        if insight_type:
            query = query.where(InsightModel.insight_type == insight_type.value)

        if category:
            query = query.where(InsightModel.category == category)

        if min_confidence is not None:
            query = query.where(InsightModel.confidence >= min_confidence)

        if user_validated is not None:
            query = query.where(InsightModel.user_validated == user_validated)

        if search_query:
            search_pattern = f"%{search_query.lower()}%"
            query = query.where(
                or_(
                    InsightModel.title_normalized.ilike(search_pattern),
                    InsightModel.description.ilike(search_pattern),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query)

        # Order
        order_column = getattr(InsightModel, order_by, InsightModel.created_at)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Pagination
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        insights = result.scalars().all()

        return insights, total or 0

    async def update(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        updates: dict[str, Any],
    ) -> InsightModel | None:
        """Update an insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID
            updates: Fields to update

        Returns:
            Updated InsightModel or None
        """
        insight = await self.get_by_id(insight_id, tenant_id)
        if not insight:
            return None

        # Update allowed fields
        allowed_fields = {
            "title", "description", "confidence", "category",
            "severity", "impact", "user_validated", "validation_status",
            "raw_data", "sources",
        }

        for field, value in updates.items():
            if field in allowed_fields and hasattr(insight, field):
                setattr(insight, field, value)

        # Update normalized title if title changed
        if "title" in updates:
            insight.title_normalized = self._normalize(updates["title"])

        insight.updated_at = datetime.utcnow()

        await self.session.flush()
        return insight

    async def delete(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        hard_delete: bool = False,
    ) -> bool:
        """Delete an insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID
            hard_delete: If True, permanently delete

        Returns:
            True if deleted
        """
        insight = await self.get_by_id(insight_id, tenant_id, include_deleted=True)
        if not insight:
            return False

        if hard_delete:
            await self.session.delete(insight)
        else:
            insight.is_deleted = True
            insight.deleted_at = datetime.utcnow()

        await self.session.flush()
        return True

    async def find_by_hash(
        self,
        tenant_id: UUID,
        content_hash: str,
    ) -> InsightModel | None:
        """Find insight by content hash.

        Args:
            tenant_id: Tenant ID
            content_hash: Content hash

        Returns:
            Existing insight or None
        """
        query = select(InsightModel).where(
            InsightModel.tenant_id == tenant_id,
            InsightModel.content_hash == content_hash,
            InsightModel.is_deleted == False,
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_similar(
        self,
        tenant_id: UUID,
        title: str,
        insight_type: InsightType,
        threshold: float = 0.85,
    ) -> list[InsightModel]:
        """Find similar insights by title.

        Args:
            tenant_id: Tenant ID
            title: Title to match
            insight_type: Insight type
            threshold: Similarity threshold

        Returns:
            List of similar insights
        """
        normalized = self._normalize(title)

        # Find exact or near matches
        query = select(InsightModel).where(
            InsightModel.tenant_id == tenant_id,
            InsightModel.insight_type == insight_type.value,
            InsightModel.is_deleted == False,
            InsightModel.title_normalized == normalized,
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(
        self,
        tenant_id: UUID,
        document_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Get insight statistics.

        Args:
            tenant_id: Tenant ID
            document_id: Optional document filter

        Returns:
            Statistics dictionary
        """
        base_filter = [
            InsightModel.tenant_id == tenant_id,
            InsightModel.is_deleted == False,
        ]

        if document_id:
            base_filter.append(InsightModel.document_id == document_id)

        # Total count
        total_query = select(func.count()).where(*base_filter)
        total = await self.session.scalar(total_query)

        # Count by type
        type_query = (
            select(InsightModel.insight_type, func.count())
            .where(*base_filter)
            .group_by(InsightModel.insight_type)
        )
        type_result = await self.session.execute(type_query)
        by_type = dict(type_result.all())

        # Average confidence
        avg_conf_query = select(func.avg(InsightModel.confidence)).where(*base_filter)
        avg_confidence = await self.session.scalar(avg_conf_query)

        # Validated count
        validated_query = select(func.count()).where(
            *base_filter,
            InsightModel.user_validated == True,
        )
        validated = await self.session.scalar(validated_query)

        return {
            "total_insights": total or 0,
            "by_type": by_type,
            "average_confidence": round(avg_confidence or 0, 3),
            "validated_count": validated or 0,
            "validation_rate": round((validated or 0) / max(total or 1, 1), 3),
        }

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        return text.lower().strip()

    def _compute_hash(self, insight: Insight) -> str:
        """Compute content hash for deduplication."""
        content = f"{insight.tenant_id}:{insight.insight_type.value}:{self._normalize(insight.title)}:{insight.document_id}"
        return hashlib.sha256(content.encode()).hexdigest()
```

### 4. Create `/services/insight-engine/src/aswa_insight/repository/deduplication.py`
Deduplication service:

```python
from dataclasses import dataclass
from typing import Any
from uuid import UUID
import hashlib
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from .insight_repo import InsightRepository
from .models import InsightModel
from aswa_insight.models.insights import Insight, InsightType
from aswa_insight.scoring.confidence import ConfidenceAggregator

logger = structlog.get_logger()


@dataclass
class DuplicateMatch:
    """A potential duplicate match."""
    existing_insight: InsightModel
    similarity_score: float
    match_reason: str


class DuplicateDetector:
    """Detect duplicate insights."""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
    ):
        self.similarity_threshold = similarity_threshold

    def compute_hash(self, insight: Insight) -> str:
        """Compute content hash for exact matching."""
        content = (
            f"{insight.tenant_id}:"
            f"{insight.insight_type.value}:"
            f"{self._normalize(insight.title)}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def compute_similarity(
        self,
        insight1: Insight | InsightModel,
        insight2: Insight | InsightModel,
    ) -> float:
        """Compute similarity between two insights."""
        # Title similarity (Jaccard)
        title1 = self._normalize(self._get_title(insight1))
        title2 = self._normalize(self._get_title(insight2))

        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        title_sim = intersection / union if union > 0 else 0.0

        # Type must match
        type1 = self._get_type(insight1)
        type2 = self._get_type(insight2)
        if type1 != type2:
            return 0.0

        # Category similarity (bonus if same)
        cat1 = self._get_category(insight1)
        cat2 = self._get_category(insight2)
        category_bonus = 0.1 if cat1 and cat1 == cat2 else 0.0

        return min(1.0, title_sim + category_bonus)

    def _normalize(self, text: str) -> str:
        return text.lower().strip()

    def _get_title(self, insight: Insight | InsightModel) -> str:
        if isinstance(insight, InsightModel):
            return insight.title
        return insight.title

    def _get_type(self, insight: Insight | InsightModel) -> str:
        if isinstance(insight, InsightModel):
            return insight.insight_type
        return insight.insight_type.value

    def _get_category(self, insight: Insight | InsightModel) -> str | None:
        return insight.category


class DeduplicationService:
    """Service for deduplicating insights."""

    def __init__(
        self,
        session: AsyncSession,
        detector: DuplicateDetector | None = None,
    ):
        self.session = session
        self.repository = InsightRepository(session)
        self.detector = detector or DuplicateDetector()
        self.confidence_aggregator = ConfidenceAggregator()

    async def check_and_store(
        self,
        insight: Insight,
        merge_duplicates: bool = True,
    ) -> tuple[InsightModel, bool]:
        """Check for duplicates and store insight.

        Args:
            insight: Insight to check and store
            merge_duplicates: If True, merge with existing duplicate

        Returns:
            Tuple of (InsightModel, is_new)
        """
        # Check for exact hash match
        content_hash = self.detector.compute_hash(insight)
        existing = await self.repository.find_by_hash(
            insight.tenant_id,
            content_hash,
        )

        if existing:
            logger.info(
                "Exact duplicate found",
                new_insight=str(insight.id),
                existing_insight=str(existing.id),
            )

            if merge_duplicates:
                await self._merge_insights(existing, insight)
            return existing, False

        # Check for similar insights
        similar = await self.repository.find_similar(
            insight.tenant_id,
            insight.title,
            insight.insight_type,
        )

        for existing_similar in similar:
            similarity = self.detector.compute_similarity(insight, existing_similar)
            if similarity >= self.detector.similarity_threshold:
                logger.info(
                    "Similar duplicate found",
                    new_insight=str(insight.id),
                    existing_insight=str(existing_similar.id),
                    similarity=similarity,
                )

                if merge_duplicates:
                    await self._merge_insights(existing_similar, insight)
                return existing_similar, False

        # No duplicate, create new
        new_model = await self.repository.create(insight)
        return new_model, True

    async def deduplicate_batch(
        self,
        insights: list[Insight],
    ) -> tuple[list[InsightModel], dict[str, int]]:
        """Deduplicate a batch of insights.

        Args:
            insights: List of insights to process

        Returns:
            Tuple of (stored_models, stats)
        """
        stored = []
        stats = {
            "total": len(insights),
            "new": 0,
            "merged": 0,
            "exact_duplicates": 0,
            "similar_duplicates": 0,
        }

        for insight in insights:
            model, is_new = await self.check_and_store(insight)
            stored.append(model)

            if is_new:
                stats["new"] += 1
            else:
                stats["merged"] += 1

        logger.info(
            "Batch deduplication complete",
            total=stats["total"],
            new=stats["new"],
            merged=stats["merged"],
        )

        return stored, stats

    async def _merge_insights(
        self,
        existing: InsightModel,
        new: Insight,
    ) -> None:
        """Merge new insight data into existing."""
        # Update confidence (take maximum or aggregate)
        new_confidence = self.confidence_aggregator.max_confidence([
            existing.confidence,
            new.confidence,
        ])
        existing.confidence = new_confidence

        # Merge sources
        existing_sources = existing.sources or []
        new_sources = [s.model_dump() for s in new.sources] if new.sources else []
        merged_sources = existing_sources + [
            s for s in new_sources if s not in existing_sources
        ]
        existing.sources = merged_sources

        # Increment merge count
        existing.merge_count += 1
        existing.updated_at = datetime.utcnow()

        await self.session.flush()

    async def find_duplicates(
        self,
        tenant_id: UUID,
        insight_type: InsightType | None = None,
    ) -> list[list[InsightModel]]:
        """Find duplicate groups in existing insights.

        Returns groups of insights that appear to be duplicates.
        """
        insights, _ = await self.repository.list_insights(
            tenant_id=tenant_id,
            insight_type=insight_type,
            limit=1000,
        )

        # Group by normalized title
        groups: dict[str, list[InsightModel]] = {}

        for insight in insights:
            key = insight.title_normalized
            if key not in groups:
                groups[key] = []
            groups[key].append(insight)

        # Return groups with more than one insight
        return [group for group in groups.values() if len(group) > 1]


from datetime import datetime  # Add to imports if not present
```

## Test Requirements

### Create `/services/insight-engine/tests/repository/__init__.py`

### Create `/services/insight-engine/tests/repository/test_insight_repo.py`
```python
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
```

### Create `/services/insight-engine/tests/repository/test_deduplication.py`
```python
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
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/repository/ -v`
2. Verify imports: `python -c "from aswa_insight.repository import *"`
3. Test database migrations with Alembic
