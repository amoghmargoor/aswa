"""Data source synchronization flows.

Provides Prefect flows for syncing documents from external data sources
like Gmail, Google Drive, Slack, and Salesforce.
"""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from prefect import flow, get_run_logger, task
from prefect.tasks import task_input_hash

from aswa_ingestion.config import settings

logger = structlog.get_logger()


@task(
    name="fetch_data_source",
    retries=2,
    retry_delay_seconds=30,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(minutes=5),
)
async def fetch_data_source(data_source_id: UUID, tenant_id: UUID) -> dict[str, Any]:
    """Fetch data source configuration from database.

    Args:
        data_source_id: Data source ID
        tenant_id: Tenant ID

    Returns:
        Data source configuration dict

    Raises:
        ValueError: If data source not found
    """
    from aswa_common.db import get_async_session

    async with get_async_session() as session:
        from sqlalchemy import select
        from aswa_common.db.models import DataSource

        stmt = select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == tenant_id,
        )
        result = await session.execute(stmt)
        ds = result.scalar_one_or_none()

        if not ds:
            raise ValueError(f"Data source {data_source_id} not found")

        return {
            "id": str(ds.id),
            "tenant_id": str(ds.tenant_id),
            "source_type": ds.source_type,
            "name": ds.name,
            "config": ds.config or {},
            "sync_cursor": ds.sync_cursor,
            "sync_frequency_minutes": ds.sync_frequency_minutes,
        }


@task(name="create_connector", retries=1)
async def create_connector(
    data_source: dict[str, Any], tenant_id: UUID
) -> Any:
    """Create and authenticate connector for data source.

    Args:
        data_source: Data source configuration
        tenant_id: Tenant ID

    Returns:
        Authenticated connector instance

    Raises:
        ValueError: If authentication fails
    """
    prefect_logger = get_run_logger()

    # Import connector dynamically based on type
    source_type = data_source["source_type"]
    config = data_source.get("config", {})

    prefect_logger.info(f"Creating connector for {source_type}")

    # This would use a real connector factory in production
    # For now, we'll use a mock interface
    try:
        from aswa_ingestion.connectors import ConnectorFactory

        connector = await ConnectorFactory.create(
            source_type=source_type,
            credentials=config.get("credentials", {}),
            settings=config.get("settings", {}),
            tenant_id=tenant_id,
        )

        if not await connector.authenticate():
            raise ValueError(f"Failed to authenticate {source_type} connector")

        return connector
    except ImportError:
        # Return mock for testing
        prefect_logger.warning("Using mock connector - ConnectorFactory not available")
        return MockConnector(source_type, config)


class MockConnector:
    """Mock connector for testing."""

    def __init__(self, source_type: str, config: dict[str, Any]) -> None:
        self.source_type = source_type
        self.config = config

    async def authenticate(self) -> bool:
        return True

    async def fetch_documents(
        self, cursor: Any, batch_size: int
    ):
        """Mock document fetch."""
        yield [], None


@task(
    name="sync_documents",
    retries=1,
    timeout_seconds=3600,  # 1 hour timeout
)
async def sync_documents(
    connector: Any,
    data_source: dict[str, Any],
    tenant_id: UUID,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Sync documents from data source.

    Args:
        connector: Authenticated connector
        data_source: Data source configuration
        tenant_id: Tenant ID
        batch_size: Documents per batch

    Returns:
        Sync statistics and cursor
    """
    from aswa_common.db import get_async_session

    prefect_logger = get_run_logger()

    # Parse existing cursor
    cursor = None
    if data_source.get("sync_cursor"):
        try:
            cursor = json.loads(data_source["sync_cursor"])
        except json.JSONDecodeError:
            prefect_logger.warning("Invalid sync cursor, starting fresh")

    stats = {
        "documents_fetched": 0,
        "documents_created": 0,
        "documents_updated": 0,
        "documents_skipped": 0,
        "errors": 0,
    }

    last_cursor = cursor

    async with get_async_session() as session:
        try:
            async for batch, new_cursor in connector.fetch_documents(cursor, batch_size):
                for doc in batch:
                    stats["documents_fetched"] += 1

                    try:
                        # Check for duplicates by external ID
                        from sqlalchemy import select
                        from aswa_common.db.models import Document

                        stmt = select(Document).where(
                            Document.tenant_id == tenant_id,
                            Document.external_id == doc.external_id,
                        )
                        result = await session.execute(stmt)
                        existing = result.scalar_one_or_none()

                        if existing:
                            if hasattr(doc, "version_hash") and existing.version_hash == doc.version_hash:
                                stats["documents_skipped"] += 1
                                continue
                            else:
                                # Update existing document
                                existing.title = doc.title
                                existing.content_type = doc.content_type
                                existing.version_hash = getattr(doc, "version_hash", None)
                                existing.updated_at = datetime.utcnow()
                                existing.processed_status = "pending"
                                stats["documents_updated"] += 1
                        else:
                            # Create new document
                            new_doc = Document(
                                tenant_id=tenant_id,
                                data_source_id=UUID(data_source["id"]),
                                external_id=doc.external_id,
                                title=doc.title,
                                content_type=doc.content_type,
                                version_hash=getattr(doc, "version_hash", None),
                                processed_status="pending",
                            )
                            session.add(new_doc)
                            stats["documents_created"] += 1

                    except Exception as e:
                        prefect_logger.error(f"Failed to process document: {e}")
                        stats["errors"] += 1

                last_cursor = new_cursor
                await session.commit()
                prefect_logger.info(f"Processed batch: {stats}")

        except Exception as e:
            prefect_logger.error(f"Sync error: {e}")
            await session.rollback()
            raise

    return {
        "stats": stats,
        "cursor": last_cursor,
    }


@task(name="update_sync_status")
async def update_sync_status(
    data_source_id: UUID,
    tenant_id: UUID,
    result: dict[str, Any] | None,
    error: str | None = None,
) -> None:
    """Update data source sync status in database.

    Args:
        data_source_id: Data source ID
        tenant_id: Tenant ID
        result: Sync result with stats and cursor
        error: Error message if sync failed
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import update
    from aswa_common.db.models import DataSource

    async with get_async_session() as session:
        update_data: dict[str, Any] = {
            "last_sync_at": datetime.utcnow(),
            "error_message": error,
        }

        if result and result.get("cursor"):
            update_data["sync_cursor"] = json.dumps(result["cursor"])

        if error:
            update_data["status"] = "error"
        else:
            update_data["status"] = "active"

        stmt = (
            update(DataSource)
            .where(
                DataSource.id == data_source_id,
                DataSource.tenant_id == tenant_id,
            )
            .values(**update_data)
        )
        await session.execute(stmt)
        await session.commit()


@task(name="queue_documents_for_processing")
async def queue_documents_for_processing(
    tenant_id: UUID,
    data_source_id: UUID | None = None,
    limit: int = 1000,
) -> int:
    """Queue pending documents for background processing.

    Args:
        tenant_id: Tenant ID
        data_source_id: Optional data source filter
        limit: Maximum documents to queue

    Returns:
        Number of documents queued
    """
    import redis.asyncio as redis
    from aswa_common.db import get_async_session
    from sqlalchemy import select
    from aswa_common.db.models import Document

    async with get_async_session() as session:
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.processed_status == "pending",
            )
            .limit(limit)
        )

        if data_source_id:
            stmt = stmt.where(Document.data_source_id == data_source_id)

        result = await session.execute(stmt)
        pending_docs = result.scalars().all()

        if not pending_docs:
            return 0

    # Queue for processing
    try:
        redis_client = redis.from_url(settings.redis.url)

        payloads = [
            json.dumps({"document_id": str(doc.id), "tenant_id": str(tenant_id)})
            for doc in pending_docs
        ]

        # Use Redis list as simple queue
        await redis_client.rpush("document_processing", *payloads)
        await redis_client.aclose()

        return len(pending_docs)
    except Exception as e:
        logger.warning(f"Failed to queue documents: {e}")
        return 0


@flow(
    name="sync_data_source",
    description="Sync documents from a single data source",
    retries=1,
    retry_delay_seconds=60,
)
async def sync_data_source(
    data_source_id: UUID,
    tenant_id: UUID,
    full_sync: bool = False,
) -> dict[str, Any]:
    """Main flow to sync a data source.

    Steps:
    1. Fetch data source config
    2. Create and authenticate connector
    3. Sync documents
    4. Update sync status
    5. Queue documents for processing

    Args:
        data_source_id: Data source ID to sync
        tenant_id: Tenant ID
        full_sync: If True, ignore cursor and sync all

    Returns:
        Sync result with statistics
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"Starting sync for data source {data_source_id}")

    try:
        # Fetch data source
        data_source = await fetch_data_source(data_source_id, tenant_id)

        if full_sync:
            data_source["sync_cursor"] = None
            prefect_logger.info("Full sync requested - ignoring existing cursor")

        # Create connector
        connector = await create_connector(data_source, tenant_id)

        # Sync documents
        result = await sync_documents(connector, data_source, tenant_id)

        # Update status
        await update_sync_status(data_source_id, tenant_id, result)

        # Queue for processing
        queued = await queue_documents_for_processing(
            tenant_id, data_source_id=data_source_id
        )
        result["documents_queued"] = queued

        prefect_logger.info(f"Sync completed: {result['stats']}")
        return result

    except Exception as e:
        prefect_logger.error(f"Sync failed: {e}")
        await update_sync_status(data_source_id, tenant_id, None, str(e))
        raise


@flow(
    name="scheduled_sync_all",
    description="Scheduled sync for all active data sources",
)
async def scheduled_sync_all() -> dict[str, int]:
    """Scheduled flow to sync all active data sources.

    Runs on a schedule (e.g., every hour) to sync all active
    data sources that are due for sync based on their frequency.

    Returns:
        Results summary with success/failed/skipped counts
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import select
    from aswa_common.db.models import DataSource

    prefect_logger = get_run_logger()
    prefect_logger.info("Starting scheduled sync for all data sources")

    results = {"success": 0, "failed": 0, "skipped": 0}

    async with get_async_session() as session:
        # Find all active data sources
        stmt = select(DataSource).where(DataSource.status == "active")
        data_sources = (await session.execute(stmt)).scalars().all()

    prefect_logger.info(f"Found {len(data_sources)} active data sources")

    for ds in data_sources:
        # Check if sync is due
        if ds.last_sync_at:
            minutes_since_sync = (
                datetime.utcnow() - ds.last_sync_at
            ).total_seconds() / 60
            frequency = ds.sync_frequency_minutes or 60

            if minutes_since_sync < frequency:
                prefect_logger.debug(
                    f"Skipping {ds.id} - synced {minutes_since_sync:.0f} min ago"
                )
                results["skipped"] += 1
                continue

        try:
            await sync_data_source(ds.id, ds.tenant_id)
            results["success"] += 1
        except Exception as e:
            prefect_logger.error(f"Sync failed for {ds.id}: {e}")
            results["failed"] += 1

    prefect_logger.info(f"Scheduled sync completed: {results}")
    return results
