from typing import Any
from uuid import UUID
import httpx
import structlog

logger = structlog.get_logger()


class QueryClient:
    """Client for ASWA Query Service."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def query(
        self,
        tenant_id: UUID,
        query: str,
        user_id: str | None = None,
        document_ids: list[UUID] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a query against the query service.

        Args:
            tenant_id: Tenant ID
            query: User query
            user_id: Optional user ID for personalization
            document_ids: Optional document filter
            filters: Optional additional filters

        Returns:
            Query response
        """
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
        }

        if user_id:
            payload["user_id"] = user_id
        if document_ids:
            payload["document_ids"] = [str(d) for d in document_ids]
        if filters:
            payload["filters"] = filters

        try:
            response = await client.post("/api/v1/query", json=payload)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("Query service error", status=e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("Query service connection error", error=str(e))
            raise

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search for documents and insights.

        Args:
            tenant_id: Tenant ID
            query: Search query
            limit: Maximum results
            filters: Optional filters

        Returns:
            Search results
        """
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
            "limit": limit,
        }

        if filters:
            payload["filters"] = filters

        try:
            response = await client.post("/api/v1/search", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Search failed", error=str(e))
            raise

    async def get_insights(
        self,
        tenant_id: UUID,
        insight_types: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get recent insights.

        Args:
            tenant_id: Tenant ID
            insight_types: Optional filter by type
            limit: Maximum results

        Returns:
            Insights response
        """
        client = await self._get_client()

        params = {
            "tenant_id": str(tenant_id),
            "limit": limit,
        }

        if insight_types:
            params["types"] = ",".join(insight_types)

        try:
            response = await client.get("/api/v1/insights", params=params)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Get insights failed", error=str(e))
            raise

    async def get_digest(
        self,
        tenant_id: UUID,
        period: str = "daily",
    ) -> dict[str, Any]:
        """Get digest for tenant.

        Args:
            tenant_id: Tenant ID
            period: Digest period (daily, weekly)

        Returns:
            Digest response
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"/api/v1/digest/{tenant_id}",
                params={"period": period}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Get digest failed", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if query service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
