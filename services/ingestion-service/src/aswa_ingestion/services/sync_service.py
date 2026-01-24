"""Sync service for data source synchronization."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings
from aswa_ingestion.models.sync_job import SyncJob, SyncJobStatus

logger = get_logger(__name__)


class SyncService:
    """Orchestrates data source synchronization.

    Responsibilities:
    - Create and manage sync jobs
    - Coordinate document fetching from connectors
    - Track sync progress and status
    - Handle sync failures and retries
    """

    SYNC_LOCK_PREFIX = "sync:lock:"
    SYNC_JOB_PREFIX = "sync:job:"
    SYNC_STATUS_PREFIX = "sync:status:"

    def __init__(self, db: AsyncSession, redis: Redis):
        """Initialize sync service.

        Args:
            db: Async database session
            redis: Redis client for distributed locking and status
        """
        self.db = db
        self.redis = redis

    async def start_sync(
        self,
        data_source_id: UUID,
        tenant_id: UUID,
        full_sync: bool = False,
    ) -> SyncJob:
        """Start a new sync job for a data source.

        Args:
            data_source_id: Data source to sync
            tenant_id: Tenant ID
            full_sync: If True, sync all documents. If False, incremental sync.

        Returns:
            Created sync job

        Raises:
            ValueError: If data source not found or sync already in progress
        """
        logger.info(
            f"Starting sync for data source {data_source_id}, "
            f"tenant={tenant_id}, full_sync={full_sync}"
        )

        # Check if sync is already in progress
        lock_key = f"{self.SYNC_LOCK_PREFIX}{data_source_id}"
        lock_acquired = await self.redis.set(
            lock_key,
            "locked",
            nx=True,
            ex=settings.ingestion.sync_job_timeout_minutes * 60,
        )

        if not lock_acquired:
            raise ValueError(f"Sync already in progress for data source {data_source_id}")

        # Create sync job
        job = SyncJob(
            id=uuid4(),
            tenant_id=tenant_id,
            data_source_id=data_source_id,
            status=SyncJobStatus.PENDING,
            full_sync=full_sync,
            started_at=datetime.now(timezone.utc),
        )

        # Store job in Redis for quick access
        await self._store_job_status(job)

        logger.info(f"Sync job {job.id} created")
        return job

    async def run_sync_job(self, job_id: UUID) -> None:
        """Execute a sync job.

        This method is designed to run in the background.

        Args:
            job_id: Sync job ID to execute
        """
        logger.info(f"Executing sync job {job_id}")

        try:
            # Get job status
            job = await self._get_job_from_redis(job_id)
            if job is None:
                logger.error(f"Sync job {job_id} not found")
                return

            # Update status to running
            job.status = SyncJobStatus.RUNNING
            await self._store_job_status(job)

            # TODO: Implement actual sync logic
            # 1. Get data source configuration
            # 2. Create appropriate connector
            # 3. Fetch documents with cursor-based pagination
            # 4. Check for duplicates by content hash
            # 5. Store new/updated documents
            # 6. Queue documents for processing

            # Simulate some work for now
            logger.info(f"Sync job {job_id} processing...")

            # Mark as completed
            job.status = SyncJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            await self._store_job_status(job)

            logger.info(f"Sync job {job_id} completed successfully")

        except Exception as e:
            logger.exception(f"Sync job {job_id} failed: {e}")

            # Update job status to failed
            job = await self._get_job_from_redis(job_id)
            if job:
                job.status = SyncJobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                await self._store_job_status(job)

        finally:
            # Release lock
            job = await self._get_job_from_redis(job_id)
            if job:
                lock_key = f"{self.SYNC_LOCK_PREFIX}{job.data_source_id}"
                await self.redis.delete(lock_key)

    async def get_job(self, job_id: UUID, tenant_id: UUID) -> SyncJob | None:
        """Get sync job by ID.

        Args:
            job_id: Sync job ID
            tenant_id: Tenant ID for authorization

        Returns:
            Sync job if found and belongs to tenant
        """
        job = await self._get_job_from_redis(job_id)
        if job and job.tenant_id == tenant_id:
            return job
        return None

    async def get_data_source_status(
        self,
        data_source_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any] | None:
        """Get sync status for a data source.

        Args:
            data_source_id: Data source ID
            tenant_id: Tenant ID

        Returns:
            Status dict or None if not found
        """
        # Check if sync is in progress
        lock_key = f"{self.SYNC_LOCK_PREFIX}{data_source_id}"
        is_syncing = await self.redis.exists(lock_key)

        # Get current job if syncing
        current_job_id = None
        if is_syncing:
            # Find the running job for this data source
            # In production, we'd maintain an index
            pass

        # TODO: Get last sync time from database
        last_sync_at = None
        next_sync_at = None

        return {
            "data_source_id": data_source_id,
            "last_sync_at": last_sync_at,
            "next_sync_at": next_sync_at,
            "is_syncing": bool(is_syncing),
            "current_job_id": current_job_id,
        }

    async def list_jobs(
        self,
        tenant_id: UUID,
        data_source_id: UUID | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> dict[str, Any]:
        """List sync jobs with filtering.

        Args:
            tenant_id: Tenant ID
            data_source_id: Optional filter by data source
            status: Optional filter by status
            page: Page number
            size: Page size

        Returns:
            Paginated list of jobs
        """
        # TODO: Implement with database query
        # For now, return empty result
        return {
            "content": [],
            "total_elements": 0,
            "total_pages": 0,
            "current_page": page,
            "page_size": size,
        }

    async def cancel_job(self, job_id: UUID, tenant_id: UUID) -> None:
        """Cancel a running sync job.

        Args:
            job_id: Job ID to cancel
            tenant_id: Tenant ID for authorization

        Raises:
            ValueError: If job not found or cannot be cancelled
        """
        job = await self.get_job(job_id, tenant_id)
        if job is None:
            raise ValueError(f"Sync job {job_id} not found")

        if job.status not in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
            raise ValueError(f"Cannot cancel job in status {job.status}")

        # Mark as cancelled
        job.status = SyncJobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._store_job_status(job)

        # Release lock
        lock_key = f"{self.SYNC_LOCK_PREFIX}{job.data_source_id}"
        await self.redis.delete(lock_key)

        logger.info(f"Sync job {job_id} cancelled")

    async def _store_job_status(self, job: SyncJob) -> None:
        """Store job status in Redis.

        Args:
            job: Sync job to store
        """
        key = f"{self.SYNC_JOB_PREFIX}{job.id}"
        data = {
            "id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "data_source_id": str(job.data_source_id),
            "status": job.status.value,
            "full_sync": job.full_sync,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "documents_found": job.documents_found,
            "documents_processed": job.documents_processed,
            "documents_failed": job.documents_failed,
            "error_message": job.error_message,
        }
        await self.redis.set(key, json.dumps(data), ex=86400)  # 24 hour TTL

    async def _get_job_from_redis(self, job_id: UUID) -> SyncJob | None:
        """Get job from Redis.

        Args:
            job_id: Job ID

        Returns:
            Sync job or None
        """
        key = f"{self.SYNC_JOB_PREFIX}{job_id}"
        data = await self.redis.get(key)
        if data is None:
            return None

        job_data = json.loads(data)
        return SyncJob(
            id=UUID(job_data["id"]),
            tenant_id=UUID(job_data["tenant_id"]),
            data_source_id=UUID(job_data["data_source_id"]),
            status=SyncJobStatus(job_data["status"]),
            full_sync=job_data["full_sync"],
            started_at=(
                datetime.fromisoformat(job_data["started_at"])
                if job_data["started_at"]
                else None
            ),
            completed_at=(
                datetime.fromisoformat(job_data["completed_at"])
                if job_data["completed_at"]
                else None
            ),
            documents_found=job_data["documents_found"],
            documents_processed=job_data["documents_processed"],
            documents_failed=job_data["documents_failed"],
            error_message=job_data["error_message"],
        )
