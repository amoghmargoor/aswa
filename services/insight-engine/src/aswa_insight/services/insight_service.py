"""Insight service for managing and querying insights."""

from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger()


class InsightService:
    """Service for managing insights."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize insight service.

        Args:
            session_factory: Database session factory
        """
        self.session_factory = session_factory
        # In-memory storage for demo
        self._insights: dict[UUID, dict[str, Any]] = {}
        self._feedback: dict[UUID, list[dict[str, Any]]] = {}

    async def list_insights(
        self,
        tenant_id: UUID,
        insight_type: str | None = None,
        category: str | None = None,
        min_confidence: float = 0.0,
        status: str = "active",
        source_document_id: UUID | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List insights with filtering and pagination.

        Args:
            tenant_id: Tenant ID
            insight_type: Filter by type
            category: Filter by category
            min_confidence: Minimum confidence threshold
            status: Filter by status
            source_document_id: Filter by source document
            search: Search in title/description
            sort_by: Sort field
            sort_order: Sort direction
            page: Page number
            size: Page size

        Returns:
            Paginated response with insights
        """
        # In production, this would query the database
        # For now, return mock data

        mock_insights = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "tenant_id": str(tenant_id),
                "insight_type": "risk",
                "category": "security",
                "title": "Potential Data Breach Risk",
                "description": "Identified vulnerabilities in authentication system",
                "confidence": 0.85,
                "severity": "high",
                "impact": None,
                "source_documents": [],
                "source_chunks": [],
                "metadata": {},
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "tenant_id": str(tenant_id),
                "insight_type": "opportunity",
                "category": "growth",
                "title": "Market Expansion Opportunity",
                "description": "Potential for expansion into APAC region",
                "confidence": 0.78,
                "severity": None,
                "impact": "high",
                "source_documents": [],
                "source_chunks": [],
                "metadata": {},
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        ]

        # Apply filters
        filtered = mock_insights

        if insight_type:
            filtered = [i for i in filtered if i["insight_type"] == insight_type]

        if category:
            filtered = [i for i in filtered if i["category"] == category]

        if min_confidence > 0:
            filtered = [i for i in filtered if i["confidence"] >= min_confidence]

        if status:
            filtered = [i for i in filtered if i["status"] == status]

        if search:
            search_lower = search.lower()
            filtered = [
                i
                for i in filtered
                if search_lower in i["title"].lower()
                or search_lower in i["description"].lower()
            ]

        # Calculate pagination
        total = len(filtered)
        total_pages = (total + size - 1) // size
        start = page * size
        end = start + size

        return {
            "content": filtered[start:end],
            "page": page,
            "size": size,
            "total_elements": total,
            "total_pages": total_pages,
        }

    async def get_insight(
        self, insight_id: UUID, tenant_id: UUID
    ) -> dict[str, Any] | None:
        """Get insight by ID.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID

        Returns:
            Insight dict or None
        """
        # Check in-memory storage
        insight = self._insights.get(insight_id)
        if insight and insight.get("tenant_id") == str(tenant_id):
            return insight

        # Return mock for demo
        return {
            "id": str(insight_id),
            "tenant_id": str(tenant_id),
            "insight_type": "entity",
            "category": "organization",
            "title": "Acme Corporation",
            "description": "Major client mentioned in multiple documents",
            "confidence": 0.92,
            "severity": None,
            "impact": None,
            "source_documents": [],
            "source_chunks": [],
            "metadata": {"entity_type": "organization"},
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "feedback": await self._get_feedback(insight_id),
        }

    async def _get_feedback(self, insight_id: UUID) -> list[dict[str, Any]]:
        """Get feedback for an insight.

        Args:
            insight_id: Insight ID

        Returns:
            List of feedback entries
        """
        return self._feedback.get(insight_id, [])

    async def update_feedback(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        feedback: Literal["confirmed", "rejected"],
        comment: str | None = None,
    ) -> bool:
        """Update user feedback on an insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID
            user_id: User ID
            feedback: Feedback type
            comment: Optional comment

        Returns:
            True if updated
        """
        feedback_entry = {
            "user_id": str(user_id),
            "feedback": feedback,
            "comment": comment,
            "created_at": datetime.utcnow().isoformat(),
        }

        if insight_id not in self._feedback:
            self._feedback[insight_id] = []

        self._feedback[insight_id].append(feedback_entry)

        logger.info(
            "Feedback recorded",
            insight_id=str(insight_id),
            user_id=str(user_id),
            feedback=feedback,
        )

        return True

    async def update_status(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        status: str,
    ) -> bool:
        """Update insight status.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID
            status: New status

        Returns:
            True if updated
        """
        logger.info(
            "Status updated",
            insight_id=str(insight_id),
            status=status,
        )
        return True

    async def get_summary(
        self, tenant_id: UUID, days: int = 7
    ) -> dict[str, Any]:
        """Get insight summary statistics.

        Args:
            tenant_id: Tenant ID
            days: Number of days to include

        Returns:
            Summary statistics
        """
        # In production, this would aggregate from database
        return {
            "total_insights": 150,
            "by_type": {
                "entity": 80,
                "risk": 35,
                "opportunity": 25,
                "pattern": 10,
            },
            "by_category": {
                "security": 20,
                "financial": 30,
                "operational": 40,
                "strategic": 25,
                "compliance": 15,
                "other": 20,
            },
            "by_severity": {
                "critical": 5,
                "high": 15,
                "medium": 25,
                "low": 10,
            },
            "avg_confidence": 0.78,
            "new_today": 12,
            "new_this_week": 45,
            "confirmed_count": 89,
            "rejected_count": 12,
        }

    async def get_related_insights(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get insights related to a specific insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID
            limit: Maximum results

        Returns:
            List of related insights
        """
        # In production, this would use vector similarity or graph relationships
        return []

    async def get_trends(
        self,
        tenant_id: UUID,
        days: int = 30,
        insight_type: str | None = None,
    ) -> dict[str, Any]:
        """Get insight trends over time.

        Args:
            tenant_id: Tenant ID
            days: Number of days
            insight_type: Filter by type

        Returns:
            Trend data
        """
        # Generate mock trend data
        trend_data = []
        base_date = datetime.utcnow() - timedelta(days=days)

        for i in range(days):
            date = base_date + timedelta(days=i)
            trend_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "count": 5 + (i % 10),
                "risks": 1 + (i % 3),
                "opportunities": 1 + (i % 2),
                "entities": 3 + (i % 5),
            })

        return {
            "period_days": days,
            "daily_counts": trend_data,
            "total_new": sum(d["count"] for d in trend_data),
            "avg_per_day": sum(d["count"] for d in trend_data) / days,
            "trend_direction": "increasing",
        }

    async def create_insight(
        self,
        tenant_id: UUID,
        insight_type: str,
        category: str,
        title: str,
        description: str,
        confidence: float,
        source_documents: list[UUID],
        source_chunks: list[str],
        metadata: dict[str, Any] | None = None,
        severity: str | None = None,
        impact: str | None = None,
    ) -> dict[str, Any]:
        """Create a new insight.

        Args:
            tenant_id: Tenant ID
            insight_type: Type of insight
            category: Category
            title: Title
            description: Description
            confidence: Confidence score
            source_documents: Source document IDs
            source_chunks: Source chunk IDs
            metadata: Additional metadata
            severity: Severity (for risks)
            impact: Impact (for opportunities)

        Returns:
            Created insight
        """
        from uuid import uuid4

        insight_id = uuid4()
        now = datetime.utcnow()

        insight = {
            "id": str(insight_id),
            "tenant_id": str(tenant_id),
            "insight_type": insight_type,
            "category": category,
            "title": title,
            "description": description,
            "confidence": confidence,
            "severity": severity,
            "impact": impact,
            "source_documents": [str(d) for d in source_documents],
            "source_chunks": source_chunks,
            "metadata": metadata or {},
            "status": "active",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        self._insights[insight_id] = insight

        logger.info(
            "Insight created",
            insight_id=str(insight_id),
            type=insight_type,
            category=category,
        )

        return insight

    async def delete_insight(
        self, insight_id: UUID, tenant_id: UUID
    ) -> bool:
        """Delete an insight.

        Args:
            insight_id: Insight ID
            tenant_id: Tenant ID

        Returns:
            True if deleted
        """
        if insight_id in self._insights:
            del self._insights[insight_id]
            logger.info("Insight deleted", insight_id=str(insight_id))
            return True
        return False
