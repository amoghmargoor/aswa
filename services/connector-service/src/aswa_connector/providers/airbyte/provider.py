"""Airbyte connector provider implementation."""

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

from aswa_connector.config import settings
from aswa_connector.framework.base import ConnectorProvider
from aswa_connector.framework.models import (
    ConnectorDefinition,
    ConnectorType,
    ConnectionConfig,
    Connection,
    ConnectionStatus,
    ConnectionTestResult,
    SyncJob,
    SyncJobStatus,
    SyncRecord,
)
from aswa_connector.providers.airbyte.client import AirbyteClient
from aswa_connector.providers.airbyte.source_configs import (
    get_connector_definition,
    get_all_connector_definitions,
    get_source_definition_id,
    build_source_config,
)

logger = get_logger(__name__)


class AirbyteProvider(ConnectorProvider):
    """Airbyte implementation of ConnectorProvider.

    Uses Airbyte's API to manage sources, connections, and syncs.
    Handles mapping between our models and Airbyte's models.
    """

    def __init__(self):
        """Initialize Airbyte provider."""
        self.client = AirbyteClient()
        self._workspace_id: str | None = None
        self._destination_id: str | None = None

    @property
    def name(self) -> str:
        """Get provider name."""
        return "airbyte"

    async def initialize(self) -> None:
        """Initialize the provider.

        Creates or gets the workspace and destination.
        """
        logger.info("Initializing Airbyte provider")

        # Check Airbyte health
        if not await self.client.health_check():
            logger.warning("Airbyte server not available, will retry on first use")
            return

        # Get or create workspace
        await self._ensure_workspace()

        # Get or create webhook destination
        await self._ensure_destination()

        logger.info(
            f"Airbyte provider initialized: workspace={self._workspace_id}, "
            f"destination={self._destination_id}"
        )

    async def shutdown(self) -> None:
        """Shutdown the provider."""
        await self.client.close()

    async def _ensure_workspace(self) -> None:
        """Ensure workspace exists."""
        if settings.airbyte.workspace_id:
            self._workspace_id = settings.airbyte.workspace_id
            return

        # List existing workspaces
        workspaces = await self.client.list_workspaces()
        for ws in workspaces:
            if ws.get("name") == settings.airbyte.workspace_name:
                self._workspace_id = ws["workspaceId"]
                logger.info(f"Found existing workspace: {self._workspace_id}")
                return

        # Create new workspace
        workspace = await self.client.create_workspace(settings.airbyte.workspace_name)
        self._workspace_id = workspace["workspaceId"]
        logger.info(f"Created workspace: {self._workspace_id}")

    async def _ensure_destination(self) -> None:
        """Ensure webhook destination exists."""
        if not self._workspace_id:
            return

        # Get destination definitions to find webhook
        dest_defs = await self.client.list_destination_definitions(self._workspace_id)
        webhook_def_id = None
        for dest_def in dest_defs:
            if "webhook" in dest_def.get("name", "").lower():
                webhook_def_id = dest_def["destinationDefinitionId"]
                break

        if not webhook_def_id:
            logger.warning("Webhook destination not found in Airbyte")
            return

        # For now, we'll create destination on-demand per connection
        # to avoid issues with shared destinations

    # Connector discovery

    async def list_available_connectors(self) -> list[ConnectorDefinition]:
        """List all available connector types."""
        return get_all_connector_definitions()

    async def get_connector_definition(
        self,
        connector_type: str,
    ) -> ConnectorDefinition | None:
        """Get definition for a specific connector type."""
        try:
            ct = ConnectorType(connector_type)
            return get_connector_definition(ct)
        except ValueError:
            return None

    # Connection management

    async def create_connection(
        self,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Create a new connection."""
        logger.info(
            f"Creating connection: tenant={tenant_id}, "
            f"type={config.connector_type}, name={config.name}"
        )

        if not self._workspace_id:
            await self._ensure_workspace()

        # Get source definition ID
        source_def_id = get_source_definition_id(config.connector_type)
        if not source_def_id:
            raise ValueError(f"Unknown connector type: {config.connector_type}")

        # Build Airbyte source config
        if isinstance(config.credentials, dict):
            creds = config.credentials
        else:
            creds = {
                "access_token": config.credentials.access_token,
                "refresh_token": config.credentials.refresh_token,
            }

        source_config = build_source_config(
            config.connector_type,
            creds,
            config.config,
        )

        # Create source in Airbyte
        source_name = f"{tenant_id}_{config.name}_{uuid4().hex[:8]}"
        source = await self.client.create_source(
            workspace_id=self._workspace_id,
            source_definition_id=source_def_id,
            name=source_name,
            connection_configuration=source_config,
        )

        source_id = source["sourceId"]
        logger.info(f"Created Airbyte source: {source_id}")

        # Create our connection record
        now = datetime.now(timezone.utc)
        connection = Connection(
            id=uuid4(),
            tenant_id=tenant_id,
            connector_type=config.connector_type,
            name=config.name,
            status=ConnectionStatus.PENDING,
            config=config.config,
            sync_schedule=config.sync_schedule,
            sync_mode=config.sync_mode,
            created_at=now,
            updated_at=now,
            provider_source_id=source_id,
        )

        # Note: Connection record should be saved by the caller
        # This provider just handles Airbyte operations

        return connection

    async def get_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> Connection | None:
        """Get a connection by ID.

        Note: This should be implemented with database lookup.
        The Airbyte provider doesn't store connection mappings.
        """
        # This would be implemented by the service layer
        # using database queries
        raise NotImplementedError(
            "Connection lookup should be done by service layer"
        )

    async def list_connections(
        self,
        tenant_id: UUID,
        connector_type: str | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List connections for a tenant.

        Note: This should be implemented with database lookup.
        """
        raise NotImplementedError(
            "Connection listing should be done by service layer"
        )

    async def update_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        config: ConnectionConfig,
    ) -> Connection:
        """Update a connection."""
        raise NotImplementedError(
            "Connection update should be done by service layer"
        )

    async def delete_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Delete a connection."""
        raise NotImplementedError(
            "Connection deletion should be done by service layer"
        )

    async def delete_airbyte_source(self, source_id: str) -> None:
        """Delete Airbyte source.

        Args:
            source_id: Airbyte source ID
        """
        logger.info(f"Deleting Airbyte source: {source_id}")
        await self.client.delete_source(source_id)

    async def test_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> ConnectionTestResult:
        """Test a connection."""
        raise NotImplementedError(
            "Use test_airbyte_source with source_id directly"
        )

    async def test_airbyte_source(self, source_id: str) -> ConnectionTestResult:
        """Test Airbyte source connection.

        Args:
            source_id: Airbyte source ID

        Returns:
            Test result
        """
        logger.info(f"Testing Airbyte source: {source_id}")

        try:
            result = await self.client.check_source(source_id)
            success = result.get("status") == "succeeded"
            message = result.get("message", "Connection test completed")

            return ConnectionTestResult(
                success=success,
                message=message,
                details=result,
            )
        except Exception as e:
            logger.exception(f"Source test failed: {e}")
            return ConnectionTestResult(
                success=False,
                message=str(e),
            )

    # Sync operations

    async def trigger_sync(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        full_refresh: bool = False,
    ) -> SyncJob:
        """Trigger a sync for a connection."""
        raise NotImplementedError(
            "Use trigger_airbyte_sync with connection mapping"
        )

    async def trigger_airbyte_sync(
        self,
        airbyte_connection_id: str,
        our_connection_id: UUID,
        tenant_id: UUID,
        full_refresh: bool = False,
    ) -> SyncJob:
        """Trigger Airbyte sync.

        Args:
            airbyte_connection_id: Airbyte connection ID
            our_connection_id: Our connection ID
            tenant_id: Tenant ID
            full_refresh: Whether to do full refresh

        Returns:
            Sync job
        """
        logger.info(
            f"Triggering sync: airbyte_connection={airbyte_connection_id}, "
            f"full_refresh={full_refresh}"
        )

        if full_refresh:
            result = await self.client.trigger_reset(airbyte_connection_id)
        else:
            result = await self.client.trigger_sync(airbyte_connection_id)

        job_id = result.get("job", {}).get("id")

        return SyncJob(
            id=uuid4(),
            connection_id=our_connection_id,
            tenant_id=tenant_id,
            status=SyncJobStatus.RUNNING,
            sync_mode="full_refresh" if full_refresh else "incremental",
            started_at=datetime.now(timezone.utc),
            provider_job_id=str(job_id) if job_id else None,
        )

    async def get_sync_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> SyncJob | None:
        """Get sync job status."""
        raise NotImplementedError(
            "Use get_airbyte_job with job ID"
        )

    async def get_airbyte_job(
        self,
        airbyte_job_id: int,
        our_job_id: UUID,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> SyncJob:
        """Get Airbyte job status.

        Args:
            airbyte_job_id: Airbyte job ID
            our_job_id: Our job ID
            connection_id: Our connection ID
            tenant_id: Tenant ID

        Returns:
            Sync job with updated status
        """
        result = await self.client.get_job(airbyte_job_id)
        job_data = result.get("job", {})

        # Map Airbyte status to our status
        airbyte_status = job_data.get("status", "").lower()
        status_mapping = {
            "pending": SyncJobStatus.PENDING,
            "running": SyncJobStatus.RUNNING,
            "incomplete": SyncJobStatus.RUNNING,
            "succeeded": SyncJobStatus.COMPLETED,
            "failed": SyncJobStatus.FAILED,
            "cancelled": SyncJobStatus.CANCELLED,
        }
        status = status_mapping.get(airbyte_status, SyncJobStatus.PENDING)

        # Get attempts for records synced
        attempts = result.get("attempts", [])
        records_synced = 0
        bytes_synced = 0
        for attempt in attempts:
            attempt_info = attempt.get("attempt", {})
            records_synced += attempt_info.get("recordsSynced", 0)
            bytes_synced += attempt_info.get("bytesSynced", 0)

        return SyncJob(
            id=our_job_id,
            connection_id=connection_id,
            tenant_id=tenant_id,
            status=status,
            started_at=datetime.fromtimestamp(
                job_data.get("createdAt", 0) / 1000, tz=timezone.utc
            ),
            completed_at=datetime.fromtimestamp(
                job_data.get("updatedAt", 0) / 1000, tz=timezone.utc
            ) if status in [SyncJobStatus.COMPLETED, SyncJobStatus.FAILED] else None,
            records_synced=records_synced,
            bytes_synced=bytes_synced,
            error_message=job_data.get("failureReason"),
            provider_job_id=str(airbyte_job_id),
        )

    async def list_sync_jobs(
        self,
        tenant_id: UUID,
        connection_id: UUID | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List sync jobs."""
        raise NotImplementedError(
            "Job listing should be done by service layer"
        )

    async def cancel_sync(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Cancel a running sync job."""
        raise NotImplementedError(
            "Use cancel_airbyte_job with job ID"
        )

    async def cancel_airbyte_job(self, airbyte_job_id: int) -> None:
        """Cancel Airbyte job.

        Args:
            airbyte_job_id: Airbyte job ID
        """
        logger.info(f"Cancelling Airbyte job: {airbyte_job_id}")
        await self.client.cancel_job(airbyte_job_id)

    async def get_sync_records(
        self,
        job_id: UUID,
        tenant_id: UUID,
    ) -> AsyncIterator[SyncRecord]:
        """Get records from a completed sync.

        Note: Airbyte uses webhooks/destinations instead.
        Records are received via the webhook handler.
        """
        raise NotImplementedError(
            "Airbyte uses webhooks for data delivery"
        )
        yield  # Make this a generator

    # Credential management

    async def update_credentials(
        self,
        connection_id: UUID,
        tenant_id: UUID,
        credentials: dict[str, Any],
    ) -> None:
        """Update credentials for a connection."""
        raise NotImplementedError(
            "Use update_airbyte_source_credentials with source_id"
        )

    async def update_airbyte_source_credentials(
        self,
        source_id: str,
        connector_type: ConnectorType,
        credentials: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        """Update Airbyte source credentials.

        Args:
            source_id: Airbyte source ID
            connector_type: Connector type
            credentials: New credentials
            config: Source configuration
        """
        logger.info(f"Updating credentials for source: {source_id}")

        source_config = build_source_config(
            connector_type,
            credentials,
            config,
        )

        # Get current source to preserve name
        source = await self.client.get_source(source_id)

        await self.client.update_source(
            source_id=source_id,
            name=source["name"],
            connection_configuration=source_config,
        )
