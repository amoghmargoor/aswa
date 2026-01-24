"""Airbyte API client."""

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from aswa_common.logging import get_logger

from aswa_connector.config import settings

logger = get_logger(__name__)


class AirbyteClient:
    """Client for Airbyte API.

    Wraps the Airbyte Configuration API for managing
    sources, destinations, connections, and jobs.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize Airbyte client.

        Args:
            api_url: Airbyte API URL
            api_key: Optional API key for authentication
        """
        self.api_url = (api_url or settings.airbyte.api_url).rstrip("/")
        self.api_key = api_key or settings.airbyte.api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make API request.

        Args:
            method: HTTP method
            path: API path
            json: Request body
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        client = await self._get_client()
        response = await client.request(method, path, json=json, params=params)
        response.raise_for_status()
        return response.json()

    # Workspace operations

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """List all workspaces."""
        result = await self._request("POST", "/v1/workspaces/list")
        return result.get("workspaces", [])

    async def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        """Get workspace by ID."""
        return await self._request(
            "POST",
            "/v1/workspaces/get",
            json={"workspaceId": workspace_id},
        )

    async def create_workspace(self, name: str) -> dict[str, Any]:
        """Create a new workspace."""
        return await self._request(
            "POST",
            "/v1/workspaces/create",
            json={"name": name},
        )

    # Source definition operations

    async def list_source_definitions(
        self,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """List available source definitions."""
        result = await self._request(
            "POST",
            "/v1/source_definitions/list_for_workspace",
            json={"workspaceId": workspace_id},
        )
        return result.get("sourceDefinitions", [])

    async def get_source_definition_spec(
        self,
        workspace_id: str,
        source_definition_id: str,
    ) -> dict[str, Any]:
        """Get source definition specification."""
        return await self._request(
            "POST",
            "/v1/source_definition_specifications/get",
            json={
                "workspaceId": workspace_id,
                "sourceDefinitionId": source_definition_id,
            },
        )

    # Source operations

    async def create_source(
        self,
        workspace_id: str,
        source_definition_id: str,
        name: str,
        connection_configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new source."""
        return await self._request(
            "POST",
            "/v1/sources/create",
            json={
                "workspaceId": workspace_id,
                "sourceDefinitionId": source_definition_id,
                "name": name,
                "connectionConfiguration": connection_configuration,
            },
        )

    async def get_source(self, source_id: str) -> dict[str, Any]:
        """Get source by ID."""
        return await self._request(
            "POST",
            "/v1/sources/get",
            json={"sourceId": source_id},
        )

    async def update_source(
        self,
        source_id: str,
        name: str,
        connection_configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Update source configuration."""
        return await self._request(
            "POST",
            "/v1/sources/update",
            json={
                "sourceId": source_id,
                "name": name,
                "connectionConfiguration": connection_configuration,
            },
        )

    async def delete_source(self, source_id: str) -> None:
        """Delete a source."""
        await self._request(
            "POST",
            "/v1/sources/delete",
            json={"sourceId": source_id},
        )

    async def check_source(self, source_id: str) -> dict[str, Any]:
        """Check source connection."""
        return await self._request(
            "POST",
            "/v1/sources/check_connection",
            json={"sourceId": source_id},
        )

    async def discover_source_schema(self, source_id: str) -> dict[str, Any]:
        """Discover source schema (streams)."""
        return await self._request(
            "POST",
            "/v1/sources/discover_schema",
            json={"sourceId": source_id},
        )

    # Destination operations

    async def create_destination(
        self,
        workspace_id: str,
        destination_definition_id: str,
        name: str,
        connection_configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new destination."""
        return await self._request(
            "POST",
            "/v1/destinations/create",
            json={
                "workspaceId": workspace_id,
                "destinationDefinitionId": destination_definition_id,
                "name": name,
                "connectionConfiguration": connection_configuration,
            },
        )

    async def get_destination(self, destination_id: str) -> dict[str, Any]:
        """Get destination by ID."""
        return await self._request(
            "POST",
            "/v1/destinations/get",
            json={"destinationId": destination_id},
        )

    async def list_destination_definitions(
        self,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        """List available destination definitions."""
        result = await self._request(
            "POST",
            "/v1/destination_definitions/list_for_workspace",
            json={"workspaceId": workspace_id},
        )
        return result.get("destinationDefinitions", [])

    # Connection operations

    async def create_connection(
        self,
        source_id: str,
        destination_id: str,
        name: str,
        sync_catalog: dict[str, Any],
        schedule: dict[str, Any] | None = None,
        namespace_definition: str = "source",
        status: str = "active",
    ) -> dict[str, Any]:
        """Create a connection between source and destination."""
        payload: dict[str, Any] = {
            "sourceId": source_id,
            "destinationId": destination_id,
            "name": name,
            "syncCatalog": sync_catalog,
            "namespaceDefinition": namespace_definition,
            "status": status,
        }

        if schedule:
            payload["schedule"] = schedule

        return await self._request("POST", "/v1/connections/create", json=payload)

    async def get_connection(self, connection_id: str) -> dict[str, Any]:
        """Get connection by ID."""
        return await self._request(
            "POST",
            "/v1/connections/get",
            json={"connectionId": connection_id},
        )

    async def update_connection(
        self,
        connection_id: str,
        sync_catalog: dict[str, Any] | None = None,
        schedule: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Update connection."""
        payload: dict[str, Any] = {"connectionId": connection_id}

        if sync_catalog:
            payload["syncCatalog"] = sync_catalog
        if schedule:
            payload["schedule"] = schedule
        if status:
            payload["status"] = status

        return await self._request("POST", "/v1/connections/update", json=payload)

    async def delete_connection(self, connection_id: str) -> None:
        """Delete a connection."""
        await self._request(
            "POST",
            "/v1/connections/delete",
            json={"connectionId": connection_id},
        )

    # Sync/Job operations

    async def trigger_sync(self, connection_id: str) -> dict[str, Any]:
        """Trigger a sync job."""
        return await self._request(
            "POST",
            "/v1/connections/sync",
            json={"connectionId": connection_id},
        )

    async def trigger_reset(self, connection_id: str) -> dict[str, Any]:
        """Trigger a reset (full refresh) job."""
        return await self._request(
            "POST",
            "/v1/connections/reset",
            json={"connectionId": connection_id},
        )

    async def get_job(self, job_id: int) -> dict[str, Any]:
        """Get job by ID."""
        return await self._request(
            "POST",
            "/v1/jobs/get",
            json={"id": job_id},
        )

    async def list_jobs(
        self,
        connection_id: str | None = None,
        status: str | None = None,
        page_size: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List jobs."""
        payload: dict[str, Any] = {
            "pagination": {"pageSize": page_size, "rowOffset": offset}
        }

        if connection_id:
            payload["configId"] = connection_id
            payload["configTypes"] = ["sync", "reset_connection"]

        return await self._request("POST", "/v1/jobs/list", json=payload)

    async def cancel_job(self, job_id: int) -> dict[str, Any]:
        """Cancel a running job."""
        return await self._request(
            "POST",
            "/v1/jobs/cancel",
            json={"id": job_id},
        )

    # Health check

    async def health_check(self) -> bool:
        """Check if Airbyte is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/v1/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Airbyte health check failed: {e}")
            return False
