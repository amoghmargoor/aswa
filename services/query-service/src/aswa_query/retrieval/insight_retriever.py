from typing import Any
from uuid import UUID
import httpx
import structlog

from aswa_query.config import Settings
from aswa_query.parser.models import ParsedQuery, QueryIntent
from .models import InsightResult

logger = structlog.get_logger()


class InsightRetriever:
    """Retrieve insights from insight-engine."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.insight_engine_url.rstrip("/")

    async def retrieve(
        self,
        query: ParsedQuery,
        tenant_id: UUID,
        limit: int = 10,
    ) -> list[InsightResult]:
        """Retrieve relevant insights based on query.

        Args:
            query: Parsed query
            tenant_id: Tenant ID
            limit: Maximum results

        Returns:
            List of insight results
        """
        # Determine insight types based on query intent
        insight_types = self._get_insight_types(query.intent)

        # Build request
        request_body = {
            "query": query.normalized_query,
            "insight_types": insight_types,
            "min_confidence": 0.5,
            "limit": limit,
        }

        # Add document scope if present
        if query.document_scope:
            request_body["document_ids"] = [str(d) for d in query.document_scope]

        # Add time range if present
        if query.time_range:
            if query.time_range.start:
                request_body["start_date"] = query.time_range.start.isoformat()
            if query.time_range.end:
                request_body["end_date"] = query.time_range.end.isoformat()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/insights/search",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    json=request_body,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                insights = []
                for item in data.get("items", []):
                    insights.append(InsightResult(
                        id=UUID(item["id"]),
                        title=item["title"],
                        description=item["description"],
                        insight_type=item["insight_type"],
                        confidence=item.get("confidence", 0.5),
                        score=item.get("score", 0.5),
                        document_id=UUID(item["document_id"]) if item.get("document_id") else None,
                        document_name=item.get("document_name"),
                        category=item.get("category"),
                        severity=item.get("severity"),
                        metadata=item.get("metadata", {}),
                    ))

                logger.info(
                    "Insights retrieved",
                    count=len(insights),
                    types=insight_types,
                )

                return insights

        except httpx.HTTPError as e:
            logger.error("Insight retrieval failed", error=str(e))
            return []

    async def get_insight_by_id(
        self,
        insight_id: UUID,
        tenant_id: UUID,
    ) -> InsightResult | None:
        """Get a specific insight by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/insights/{insight_id}",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    timeout=10.0,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                item = response.json()

                return InsightResult(
                    id=UUID(item["id"]),
                    title=item["title"],
                    description=item["description"],
                    insight_type=item["insight_type"],
                    confidence=item.get("confidence", 0.5),
                    score=1.0,
                    document_id=UUID(item["document_id"]) if item.get("document_id") else None,
                    category=item.get("category"),
                    severity=item.get("severity"),
                    metadata=item.get("metadata", {}),
                )

        except httpx.HTTPError as e:
            logger.error("Insight fetch failed", insight_id=str(insight_id), error=str(e))
            return None

    async def get_related_insights(
        self,
        insight_id: UUID,
        tenant_id: UUID,
        limit: int = 5,
    ) -> list[InsightResult]:
        """Get insights related to a given insight."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/insights/{insight_id}/related",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    params={"limit": limit},
                    timeout=10.0,
                )
                response.raise_for_status()

                return [
                    InsightResult(
                        id=UUID(item["id"]),
                        title=item["title"],
                        description=item["description"],
                        insight_type=item["insight_type"],
                        confidence=item.get("confidence", 0.5),
                        score=item.get("score", 0.5),
                    )
                    for item in response.json().get("items", [])
                ]

        except httpx.HTTPError as e:
            logger.error("Related insights fetch failed", error=str(e))
            return []

    def _get_insight_types(self, intent: QueryIntent) -> list[str] | None:
        """Map query intent to insight types."""
        intent_type_map = {
            QueryIntent.RISK: ["risk"],
            QueryIntent.OPPORTUNITY: ["opportunity"],
            QueryIntent.ENTITY: ["entity"],
            QueryIntent.TREND: ["pattern", "trend"],
        }
        return intent_type_map.get(intent)
