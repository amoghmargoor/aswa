"""Abstract base class for connector providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from aswa_connector.framework.models import (
    ConnectorDefinition,
    ConnectionConfig,
    Connection,
    ConnectionTestResult,
    SyncJob,
    SyncRecord,
)


class ConnectorProvider(ABC):
    """Abstract interface for connector providers.

    This interface defines the contract that all connector providers
    (Airbyte, custom, etc.) must implement. It enables swapping
    providers without changing the rest of the application.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get provider name."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider.

        Called once when the service starts. Use this to set up
        connections, verify credentials, create workspaces, etc.
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the provider.

        Called when the service is stopping. Use this to clean up
        resources, close connections, etc.
        """
        ...

    # Connector discovery

    @abstractmethod
    async def list_available_connectors(self) -> list[ConnectorDefinition]:
        """List all available connector types.

        Returns:
            List of connector definitions with their capabilities.
        """
        ...

    @abstractmethod
    async def get_connector_definition(
        self,
        connector_type: str,
    ) -> ConnectorDefinition | None:
        """Get definition for a specific connector type.

        Args:
            connector_type: Type identifier (e.g., "gmail", "slack")

        Returns:
            Connector definition or None if not found.
        """
        ...

    # Connection management

    @abstractmethod
    async def create_connection(
        self,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Create a new connection.

        Args:
            tenant_id: Tenant identifier
            config: Connection configuration including credentials

        Returns:
            Created connection

        Raises:
            ValueError: If configuration is invalid
            ConnectionError: If connection to source fails
        """
        ...

    @abstractmethod
    async def get_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> Connection | None:
        """Get a connection by ID.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier for authorization

        Returns:
            Connection or None if not found
        """
        ...

    @abstractmethod
    async def list_connections(
        self,
        tenant_id: UUID,
        connector_type: str | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List connections for a tenant.

        Args:
            tenant_id: Tenant identifier
            connector_type: Optional filter by connector type
            status: Optional filter by status
            page: Page number
            size: Page size

        Returns:
            Paginated list of connections
        """
        ...

    @abstractmethod
    async def update_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Update a connection.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier
            config: Updated configuration

        Returns:
            Updated connection

        Raises:
            ValueError: If connection not found
        """
        ...

    @abstractmethod
    async def delete_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Delete a connection.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier

        Raises:
            ValueError: If connection not found
        """
        ...

    @abstractmethod
    async def test_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> ConnectionTestResult:
        """Test a connection.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier

        Returns:
            Test result with success status and message
        """
        ...

    # Sync operations

    @abstractmethod
    async def trigger_sync(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        full_refresh: bool = False,
    ) -> SyncJob:
        """Trigger a sync for a connection.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier
            full_refresh: If True, sync all data. If False, incremental.

        Returns:
            Created sync job

        Raises:
            ValueError: If connection not found
        """
        ...

    @abstractmethod
    async def get_sync_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> SyncJob | None:
        """Get sync job status.

        Args:
            job_id: Job identifier
            tenant_id: Tenant identifier

        Returns:
            Sync job or None if not found
        """
        ...

    @abstractmethod
    async def list_sync_jobs(
        self,
        tenant_id: UUID,
        connection_id: UUID | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List sync jobs.

        Args:
            tenant_id: Tenant identifier
            connection_id: Optional filter by connection
            status: Optional filter by status
            page: Page number
            size: Page size

        Returns:
            Paginated list of sync jobs
        """
        ...

    @abstractmethod
    async def cancel_sync(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Cancel a running sync job.

        Args:
            job_id: Job identifier
            tenant_id: Tenant identifier

        Raises:
            ValueError: If job not found or cannot be cancelled
        """
        ...

    @abstractmethod
    async def get_sync_records(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> AsyncIterator[SyncRecord]:
        """Get records from a completed sync.

        Args:
            job_id: Job identifier
            tenant_id: Tenant identifier

        Yields:
            Sync records

        Note:
            This may not be applicable for all providers.
            Airbyte uses webhooks/destinations instead.
        """
        ...

    # Credential management

    @abstractmethod
    async def update_credentials(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        credentials: dict[str, Any],
    ) -> None:
        """Update credentials for a connection.

        Used when OAuth tokens are refreshed.

        Args:
            connection_id: Connection identifier
            tenant_id: Tenant identifier
            credentials: New credentials
        """
        ...
