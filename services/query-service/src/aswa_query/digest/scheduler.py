import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any
from uuid import UUID
import structlog

from .models import DigestConfig, Digest, DigestPeriod
from .generator import DigestGenerator

logger = structlog.get_logger()


class DigestScheduler:
    """Schedule and manage digest generation."""

    def __init__(
        self,
        generator: DigestGenerator,
        delivery_callback: Callable[[Digest], Any] | None = None,
    ):
        self.generator = generator
        self.delivery_callback = delivery_callback
        self._configs: dict[UUID, DigestConfig] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register_config(self, config: DigestConfig) -> None:
        """Register a digest configuration."""
        self._configs[config.tenant_id] = config
        logger.info(
            "Digest config registered",
            tenant_id=str(config.tenant_id),
            period=config.period,
        )

    def unregister_config(self, tenant_id: UUID) -> None:
        """Unregister a digest configuration."""
        self._configs.pop(tenant_id, None)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Digest scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Digest scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()

                for tenant_id, config in list(self._configs.items()):
                    if self._should_generate(config, now):
                        asyncio.create_task(
                            self._generate_and_deliver(config)
                        )

                # Check every minute
                await asyncio.sleep(60)

            except Exception as e:
                logger.error("Scheduler error", error=str(e))
                await asyncio.sleep(60)

    def _should_generate(self, config: DigestConfig, now: datetime) -> bool:
        """Check if digest should be generated now."""
        # Check if it's the right hour
        if now.hour != config.delivery_hour:
            return False

        # Check based on period
        if config.period == DigestPeriod.DAILY:
            return True
        elif config.period == DigestPeriod.WEEKLY:
            return now.weekday() == 0  # Monday
        elif config.period == DigestPeriod.MONTHLY:
            return now.day == 1

        return False

    async def _generate_and_deliver(self, config: DigestConfig) -> None:
        """Generate and deliver a digest."""
        try:
            digest = await self.generator.generate(config)

            if digest.is_empty:
                logger.info(
                    "Skipping empty digest",
                    tenant_id=str(config.tenant_id),
                )
                return

            if self.delivery_callback:
                await self.delivery_callback(digest)
                digest.delivered = True
                digest.delivered_at = datetime.utcnow()

            logger.info(
                "Digest delivered",
                digest_id=str(digest.id),
                tenant_id=str(config.tenant_id),
            )

        except Exception as e:
            logger.error(
                "Digest generation failed",
                tenant_id=str(config.tenant_id),
                error=str(e),
            )

    async def generate_now(self, tenant_id: UUID) -> Digest | None:
        """Generate a digest immediately."""
        config = self._configs.get(tenant_id)
        if not config:
            logger.warning("No config for tenant", tenant_id=str(tenant_id))
            return None

        return await self.generator.generate(config)
