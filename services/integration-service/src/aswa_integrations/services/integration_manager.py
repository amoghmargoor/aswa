import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.models.integration import (
    IntegrationDB,
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationStatus,
    IntegrationType,
    Base,
)
from aswa_integrations.services.credential_manager import CredentialManager
from aswa_integrations.connectors.base import BaseConnector
from aswa_integrations.connectors.jira import JiraConnector
from aswa_integrations.connectors.webhook import WebhookConnector

logger = structlog.get_logger()


class IntegrationManager:
    """Manages integration lifecycle."""

    def __init__(self):
        self.settings = get_settings()
        self.credential_manager = CredentialManager()
        self._engine = None
        self._session_factory = None
        self._connectors: dict[IntegrationType, type[BaseConnector]] = {
            IntegrationType.JIRA: JiraConnector,
            IntegrationType.WEBHOOK: WebhookConnector,
        }

    async def initialize(self) -> None:
        """Initialize the integration manager."""
        # Create database engine
        self._engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
        )

        # Create tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Initialize credential manager
        await self.credential_manager.initialize()

        logger.info("Integration manager initialized")

    async def close(self) -> None:
        """Close connections."""
        await self.credential_manager.close()
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Integration manager not initialized")
        return self._session_factory()

    async def create_integration(
        self,
        tenant_id: str,
        data: IntegrationCreate,
    ) -> IntegrationResponse:
        """Create a new integration.

        Args:
            tenant_id: Tenant identifier
            data: Integration creation data

        Returns:
            Created integration
        """
        integration_id = str(uuid.uuid4())
        credential_id = None

        # Store credentials if provided
        if data.credentials:
            credential_id = f"{tenant_id}:{integration_id}"
            await self.credential_manager.store_credentials(
                credential_id,
                data.credentials,
            )

        # Create database record
        integration = IntegrationDB(
            id=integration_id,
            tenant_id=tenant_id,
            name=data.name,
            type=data.type,
            status=IntegrationStatus.PENDING,
            config=data.config,
            credentials_id=credential_id,
        )

        async with self._get_session() as session:
            session.add(integration)
            await session.commit()
            await session.refresh(integration)

        logger.info(
            "Integration created",
            integration_id=integration_id,
            type=data.type,
            tenant_id=tenant_id,
        )

        # Test connection
        await self._test_connection(integration)

        return IntegrationResponse.model_validate(integration)

    async def get_integration(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> IntegrationResponse | None:
        """Get an integration by ID.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            Integration or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if integration:
                return IntegrationResponse.model_validate(integration)
            return None

    async def list_integrations(
        self,
        tenant_id: str,
        integration_type: IntegrationType | None = None,
        status: IntegrationStatus | None = None,
    ) -> list[IntegrationResponse]:
        """List integrations for a tenant.

        Args:
            tenant_id: Tenant identifier
            integration_type: Optional type filter
            status: Optional status filter

        Returns:
            List of integrations
        """
        async with self._get_session() as session:
            query = select(IntegrationDB).where(
                IntegrationDB.tenant_id == tenant_id
            )

            if integration_type:
                query = query.where(IntegrationDB.type == integration_type)
            if status:
                query = query.where(IntegrationDB.status == status)

            result = await session.execute(query)
            integrations = result.scalars().all()

            return [
                IntegrationResponse.model_validate(i)
                for i in integrations
            ]

    async def update_integration(
        self,
        tenant_id: str,
        integration_id: str,
        data: IntegrationUpdate,
    ) -> IntegrationResponse | None:
        """Update an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier
            data: Update data

        Returns:
            Updated integration or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return None

            # Update fields
            if data.name is not None:
                integration.name = data.name
            if data.config is not None:
                integration.config = data.config
            if data.is_enabled is not None:
                integration.is_enabled = data.is_enabled

            # Update credentials if provided
            if data.credentials and integration.credentials_id:
                await self.credential_manager.rotate_credentials(
                    integration.credentials_id,
                    data.credentials,
                )

            integration.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(integration)

            logger.info(
                "Integration updated",
                integration_id=integration_id,
            )

            return IntegrationResponse.model_validate(integration)

    async def delete_integration(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> bool:
        """Delete an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return False

            # Delete credentials
            if integration.credentials_id:
                await self.credential_manager.delete_credentials(
                    integration.credentials_id
                )

            # Delete integration
            await session.execute(
                delete(IntegrationDB).where(IntegrationDB.id == integration_id)
            )
            await session.commit()

            logger.info(
                "Integration deleted",
                integration_id=integration_id,
            )

            return True

    async def _test_connection(self, integration: IntegrationDB) -> None:
        """Test integration connection and update status.

        Args:
            integration: Integration to test
        """
        connector_class = self._connectors.get(integration.type)
        if not connector_class:
            return

        credentials = None
        if integration.credentials_id:
            credentials = await self.credential_manager.get_credentials(
                integration.credentials_id
            )

        connector = connector_class(
            config=integration.config,
            credentials=credentials,
        )

        try:
            await connector.test_connection()
            new_status = IntegrationStatus.ACTIVE
            error = None
        except Exception as e:
            new_status = IntegrationStatus.ERROR
            error = str(e)
            logger.error(
                "Integration connection test failed",
                integration_id=str(integration.id),
                error=error,
            )

        # Update status
        async with self._get_session() as session:
            await session.execute(
                update(IntegrationDB)
                .where(IntegrationDB.id == integration.id)
                .values(
                    status=new_status,
                    last_health_check=datetime.utcnow(),
                    last_error=error,
                )
            )
            await session.commit()

    async def get_connector(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> BaseConnector | None:
        """Get a configured connector for an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            Configured connector or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                    IntegrationDB.is_enabled == True,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return None

            connector_class = self._connectors.get(integration.type)
            if not connector_class:
                return None

            credentials = None
            if integration.credentials_id:
                credentials = await self.credential_manager.get_credentials(
                    integration.credentials_id
                )

            return connector_class(
                config=integration.config,
                credentials=credentials,
            )
