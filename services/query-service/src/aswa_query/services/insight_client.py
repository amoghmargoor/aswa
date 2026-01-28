from uuid import UUID
from typing import Any

import httpx
import structlog

from aswa_query.models.common import PaginatedResponse

logger = structlog.get_logger()


class InsightClient:
    """Client for the insight-engine service."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def query_insights(
        self,
        tenant_id: UUID,
        query: str | None = None,
        insight_types: list[str] | None = None,
        document_ids: list[UUID] | None = None,
        min_confidence: float = 0.5,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Query insights from insight-engine."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/insights/query",
                headers={"X-Tenant-ID": str(tenant_id)},
                json={
                    "query": query,
                    "insight_types": insight_types,
                    "document_ids": [str(d) for d in document_ids] if document_ids else None,
                    "min_confidence": min_confidence,
                    "limit": limit,
                    "offset": offset,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return PaginatedResponse(
                items=data.get("items", []),
                total=data.get("total", 0),
                limit=limit,
                offset=offset,
                has_more=data.get("has_more", False),
            )

    async def get_summary(self, tenant_id: UUID, document_id: UUID | None = None) -> dict:
        """Get insight summary."""
        async with httpx.AsyncClient() as client:
            params = {}
            if document_id:
                params["document_id"] = str(document_id)

            response = await client.get(
                f"{self.base_url}/api/v1/insights/summary",
                headers={"X-Tenant-ID": str(tenant_id)},
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_trends(self, tenant_id: UUID, days: int = 30) -> dict:
        """Get insight trends."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/insights/trends",
                headers={"X-Tenant-ID": str(tenant_id)},
                params={"days": days},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
