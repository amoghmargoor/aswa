"""Insight repository with specialized queries."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models.insight import Insight
from aswa_common.db.repositories.base import TenantScopedRepository
from aswa_common.logging import get_logger
from aswa_common.models import PageRequest, PageResponse

logger = get_logger(__name__)


class InsightRepository(TenantScopedRepository[Insight]):
    """Repository for insight-specific operations."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        """Initialize insight repository.

        Args:
            session: Async database session
            tenant_id: Tenant ID for isolation
        """
        super().__init__(session, Insight, tenant_id)

    async def find_by_type(
        self,
        insight_type: str,
        page: PageRequest,
    ) -> PageResponse[Insight]:
        """Find insights by type with pagination.

        Args:
            insight_type: Insight type (entity, risk, opportunity, pattern, etc.)
            page: Pagination request

        Returns:
            Paginated insights of specified type
        """
        logger.debug(f"Finding insights by type={insight_type} for tenant={self.tenant_id}")

        # Count total
        count_stmt = (
            select(func.count())
            .select_from(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                Insight.insight_type == insight_type,
            )
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Query with pagination
        stmt = (
            select(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                Insight.insight_type == insight_type,
            )
            .order_by(Insight.created_at.desc())
            .offset(page.page * page.size)
            .limit(page.size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        import math

        total_pages = math.ceil(total / page.size) if page.size > 0 else 0

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=total_pages,
            current_page=page.page,
            page_size=page.size,
        )

    async def find_by_documents(self, document_ids: list[UUID]) -> list[Insight]:
        """Find insights that reference specific documents.

        Args:
            document_ids: List of document IDs

        Returns:
            List of insights that reference any of the documents
        """
        logger.debug(
            f"Finding insights by {len(document_ids)} documents for tenant={self.tenant_id}"
        )
        stmt = (
            select(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                Insight.source_documents.overlap(document_ids),
            )
            .order_by(Insight.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_fulltext(
        self,
        query: str,
        page: PageRequest,
    ) -> PageResponse[Insight]:
        """Full-text search across insights.

        Args:
            query: Search query
            page: Pagination request

        Returns:
            Paginated search results
        """
        logger.debug(f"Full-text search for '{query}' in insights for tenant={self.tenant_id}")

        # PostgreSQL full-text search
        # Count matching insights
        count_stmt = (
            select(func.count())
            .select_from(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                text(
                    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')) "
                    "@@ to_tsquery('english', :query)"
                ).bindparams(query=query.replace(" ", " & ")),
            )
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Search with ranking
        stmt = (
            select(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                text(
                    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')) "
                    "@@ to_tsquery('english', :query)"
                ).bindparams(query=query.replace(" ", " & ")),
            )
            .order_by(
                text(
                    "ts_rank(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')), "
                    "to_tsquery('english', :query)) DESC"
                ).bindparams(query=query.replace(" ", " & "))
            )
            .offset(page.page * page.size)
            .limit(page.size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        import math

        total_pages = math.ceil(total / page.size) if page.size > 0 else 0

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=total_pages,
            current_page=page.page,
            page_size=page.size,
        )

    async def update_feedback(
        self,
        id: UUID,
        feedback: str,
        user_id: UUID,
        comment: str | None = None,
    ) -> None:
        """Update user feedback on an insight.

        Args:
            id: Insight ID
            feedback: Feedback type (confirmed, rejected, modified)
            user_id: User providing feedback
            comment: Optional feedback comment
        """
        logger.debug(f"Updating feedback for insight {id} by user {user_id}")
        insight = await self.get_by_id(id)
        if insight:
            insight.user_feedback = feedback
            insight.feedback_by = user_id
            insight.feedback_comment = comment
            insight.feedback_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def aggregate_by_type(self) -> dict[str, int]:
        """Aggregate insights count by type.

        Returns:
            Dictionary mapping insight_type to count
        """
        logger.debug(f"Aggregating insights by type for tenant={self.tenant_id}")
        stmt = (
            select(Insight.insight_type, func.count(Insight.id))
            .where(Insight.tenant_id == self.tenant_id)
            .group_by(Insight.insight_type)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def find_recent(self, days: int = 7, limit: int = 100) -> list[Insight]:
        """Find recent insights within specified days.

        Args:
            days: Number of days to look back
            limit: Maximum number of insights to return

        Returns:
            List of recent insights
        """
        logger.debug(
            f"Finding insights from last {days} days (limit={limit}) for tenant={self.tenant_id}"
        )
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(Insight)
            .where(
                Insight.tenant_id == self.tenant_id,
                Insight.created_at >= cutoff_date,
                Insight.status == "active",
            )
            .order_by(Insight.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
