import asyncio
from datetime import datetime
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.models.integration import IntegrationStatus

logger = structlog.get_logger()


class HealthChecker:
    """Monitors health of integrations."""

    def __init__(self, integration_manager: IntegrationManager):
        self.settings = get_settings()
        self.integration_manager = integration_manager
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the health checker."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Health checker started")

    async def stop(self) -> None:
        """Stop the health checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker stopped")

    async def _run(self) -> None:
        """Run the health check loop."""
        while self._running:
            try:
                await self._check_all_integrations()
            except Exception as e:
                logger.error("Health check failed", error=str(e))

            await asyncio.sleep(self.settings.health_check_interval)

    async def _check_all_integrations(self) -> None:
        """Check health of all active integrations."""
        # This would iterate through all tenants and their integrations
        # For now, we log a placeholder message
        logger.debug("Running health checks")

    async def check_integration(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> dict:
        """Check health of a specific integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            Health check result
        """
        start_time = datetime.utcnow()

        connector = await self.integration_manager.get_connector(
            tenant_id,
            integration_id,
        )

        if not connector:
            return {
                "status": IntegrationStatus.INACTIVE,
                "error": "Integration not found or disabled",
            }

        try:
            async with connector:
                await asyncio.wait_for(
                    connector.test_connection(),
                    timeout=self.settings.health_check_timeout,
                )

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "status": IntegrationStatus.ACTIVE,
                "latency_ms": latency,
                "checked_at": datetime.utcnow().isoformat(),
            }

        except asyncio.TimeoutError:
            return {
                "status": IntegrationStatus.ERROR,
                "error": "Connection timeout",
                "checked_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "status": IntegrationStatus.ERROR,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat(),
            }
