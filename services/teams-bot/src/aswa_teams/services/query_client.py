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
    ) -> dict[str, Any]:
        """Execute a query."""
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
        }

        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post("/api/v1/query", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Query failed", error=str(e))
            raise

    async def get_insights(
        self,
        tenant_id: UUID,
        insight_types: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get insights."""
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
