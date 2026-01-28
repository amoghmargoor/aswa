from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from .manager import CacheManager
from .keys import CacheKeyBuilder

logger = structlog.get_logger()


class InvalidationEvent:
    """An event that triggers cache invalidation."""

    def __init__(
        self,
        event_type: str,
        tenant_id: UUID,
        resource_id: UUID | None = None,
        metadata: dict | None = None,
    ):
        self.event_type = event_type
        self.tenant_id = tenant_id
        self.resource_id = resource_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()


class CacheInvalidator:
    """Handle cache invalidation based on events."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.key_builder = CacheKeyBuilder()

        # Event handlers
        self._handlers = {
            "document_updated": self._handle_document_update,
            "document_deleted": self._handle_document_delete,
            "insight_updated": self._handle_insight_update,
            "insight_deleted": self._handle_insight_delete,
            "tenant_config_changed": self._handle_tenant_config_change,
        }

    async def handle_event(self, event: InvalidationEvent) -> int:
        """Process an invalidation event.

        Args:
            event: Invalidation event

        Returns:
            Number of keys invalidated
        """
        handler = self._handlers.get(event.event_type)
        if handler:
            return await handler(event)

        logger.warning("Unknown invalidation event", event_type=event.event_type)
        return 0

    async def _handle_document_update(self, event: InvalidationEvent) -> int:
        """Handle document update - invalidate related caches."""
        return await self.cache.invalidate_document(
            event.tenant_id,
            event.resource_id,
        )

    async def _handle_document_delete(self, event: InvalidationEvent) -> int:
        """Handle document deletion."""
        return await self.cache.invalidate_document(
            event.tenant_id,
            event.resource_id,
        )

    async def _handle_insight_update(self, event: InvalidationEvent) -> int:
        """Handle insight update."""
        if event.resource_id:
            key = self.key_builder.insight_key(event.tenant_id, event.resource_id)
            await self.cache.delete(key)
            return 1
        return 0

    async def _handle_insight_delete(self, event: InvalidationEvent) -> int:
        """Handle insight deletion."""
        return await self._handle_insight_update(event)

    async def _handle_tenant_config_change(self, event: InvalidationEvent) -> int:
        """Handle tenant configuration change - full invalidation."""
        return await self.cache.invalidate_tenant(event.tenant_id)

    async def schedule_cleanup(
        self,
        tenant_id: UUID,
        delay_seconds: int = 300,
    ) -> None:
        """Schedule a cache cleanup for later.

        Args:
            tenant_id: Tenant ID
            delay_seconds: Delay before cleanup
        """
        # In production, this would use a task queue
        logger.info(
            "Cache cleanup scheduled",
            tenant_id=str(tenant_id),
            delay=delay_seconds,
        )


class CacheWarmer:
    """Pre-warm cache with common queries."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    async def warm_common_queries(
        self,
        tenant_id: UUID,
        queries: list[str],
        query_processor: Any,
    ) -> int:
        """Warm cache with common queries.

        Args:
            tenant_id: Tenant ID
            queries: List of common queries
            query_processor: Query processor to execute queries

        Returns:
            Number of queries warmed
        """
        warmed = 0

        for query in queries:
            try:
                # Execute query to populate cache
                await query_processor.process(tenant_id, query)
                warmed += 1
            except Exception as e:
                logger.warning("Failed to warm query", query=query, error=str(e))

        logger.info("Cache warming complete", warmed=warmed, total=len(queries))
        return warmed

    async def warm_from_history(
        self,
        tenant_id: UUID,
        query_processor: Any,
        limit: int = 100,
    ) -> int:
        """Warm cache from query history.

        Args:
            tenant_id: Tenant ID
            query_processor: Query processor
            limit: Max queries to warm

        Returns:
            Number of queries warmed
        """
        # Would fetch from query history service
        # For now, return 0
        return 0
