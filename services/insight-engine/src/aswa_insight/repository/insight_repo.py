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
