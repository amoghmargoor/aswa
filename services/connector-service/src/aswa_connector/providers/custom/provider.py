"""Custom connector provider implementation (stub)."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from aswa_common.logging import get_logger

from aswa_connector.framework.base import ConnectorProvider
from aswa_connector.framework.models import (
    ConnectorDefinition,
    ConnectionConfig,
    Connection,
    ConnectionTestResult,
    SyncJob,
    SyncRecord,
)

logger = get_logger(__name__)


class CustomProvider(ConnectorProvider):
    """Custom connector provider.

    This is a stub for future implementation of custom connectors
    that don't rely on Airbyte.
    """

    @property
    def name(self) -> str:
        """Get provider name."""
        return "custom"

    async def initialize(self) -> None:
        """Initialize the provider."""
        logger.info("Custom provider initialized (stub)")

    async def shutdown(self) -> None:
        """Shutdown the provider."""
        pass

    async def list_available_connectors(self) -> list[ConnectorDefinition]:
        """List all available connector types."""
        # Return empty list for now
        return []

    async def get_connector_definition(
        self,
        connector_type: str,
    ) -> ConnectorDefinition | None:
        """Get definition for a specific connector type."""
        return None

    async def create_connection(
        self,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Create a new connection."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def get_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> Connection | None:
        """Get a connection by ID."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def list_connections(
        self,
        tenant_id: UUID,
        connector_type: str | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List connections for a tenant."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def update_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Update a connection."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def delete_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Delete a connection."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def test_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> ConnectionTestResult:
        """Test a connection."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def trigger_sync(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        full_refresh: bool = False,
    ) -> SyncJob:
        """Trigger a sync for a connection."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def get_sync_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> SyncJob | None:
        """Get sync job status."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def list_sync_jobs(
        self,
        tenant_id: UUID,
        connection_id: UUID | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List sync jobs."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def cancel_sync(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Cancel a running sync job."""
        raise NotImplementedError("Custom provider not yet implemented")

    async def get_sync_records(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> AsyncIterator[SyncRecord]:
        """Get records from a completed sync."""
        raise NotImplementedError("Custom provider not yet implemented")
        yield  # Make this a generator

    async def update_credentials(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        credentials: dict[str, Any],
    ) -> None:
        """Update credentials for a connection."""
        raise NotImplementedError("Custom provider not yet implemented")
