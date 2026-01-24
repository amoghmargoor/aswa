"""Sync API endpoints for data source synchronization."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

from aswa_ingestion.dependencies import DbSession, RedisClient, TenantCtx
from aswa_ingestion.services.sync_service import SyncService

logger = get_logger(__name__)

router = APIRouter()


class SyncRequest(BaseModel):
    """Request to trigger a sync."""

    full_sync: bool = Field(
        default=False,
        description="If true, re-sync all documents. Otherwise, sync only changes since last sync.",
    )


class SyncJobResponse(BaseModel):
    """Sync job status response."""

    job_id: UUID
    data_source_id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    documents_found: int
    documents_processed: int
    documents_failed: int
    error_message: str | None


class SyncStatusResponse(BaseModel):
    """Data source sync status response."""

    data_source_id: UUID
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    is_syncing: bool
    current_job_id: UUID | None


@router.post("/data-sources/{source_id}/sync")
async def trigger_sync(
    source_id: UUID,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> SyncJobResponse:
    """Trigger synchronization for a data source.

    Args:
        source_id: Data source ID to sync
        request: Sync options
        background_tasks: FastAPI background tasks
        tenant_ctx: Tenant context from headers
        db: Database session
        redis: Redis client

    Returns:
        Sync job information
    """
    logger.info(
        f"Triggering sync for data source {source_id}, tenant={tenant_ctx.tenant_id}, "
        f"full_sync={request.full_sync}"
    )

    sync_service = SyncService(db, redis)

    try:
        job = await sync_service.start_sync(
            data_source_id=source_id,
            tenant_id=tenant_ctx.tenant_id,
            full_sync=request.full_sync,
        )

        # Run sync in background
        background_tasks.add_task(sync_service.run_sync_job, job.id)

        logger.info(f"Sync job {job.id} created for data source {source_id}")

        return SyncJobResponse(
            job_id=job.id,
            data_source_id=source_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=None,
            documents_found=0,
            documents_processed=0,
            documents_failed=0,
            error_message=None,
        )

    except ValueError as e:
        logger.warning(f"Failed to start sync: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/data-sources/{source_id}/sync/status")
async def get_sync_status(
    source_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> SyncStatusResponse:
    """Get current sync status for a data source.

    Args:
        source_id: Data source ID
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client

    Returns:
        Current sync status
    """
    logger.debug(f"Getting sync status for data source {source_id}")

    sync_service = SyncService(db, redis)
    status = await sync_service.get_data_source_status(source_id, tenant_ctx.tenant_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    return SyncStatusResponse(**status)


@router.get("/sync-jobs")
async def list_sync_jobs(
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
    data_source_id: UUID | None = None,
    status: str | None = None,
    page: int = 0,
    size: int = 20,
) -> dict[str, Any]:
    """List sync jobs with optional filtering.

    Args:
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client
        data_source_id: Filter by data source
        status: Filter by status
        page: Page number (0-based)
        size: Page size

    Returns:
        Paginated list of sync jobs
    """
    logger.debug(f"Listing sync jobs for tenant {tenant_ctx.tenant_id}")

    sync_service = SyncService(db, redis)
    result = await sync_service.list_jobs(
        tenant_id=tenant_ctx.tenant_id,
        data_source_id=data_source_id,
        status=status,
        page=page,
        size=size,
    )

    return result


@router.get("/sync-jobs/{job_id}")
async def get_sync_job(
    job_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> SyncJobResponse:
    """Get details of a specific sync job.

    Args:
        job_id: Sync job ID
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client

    Returns:
        Sync job details
    """
    logger.debug(f"Getting sync job {job_id}")

    sync_service = SyncService(db, redis)
    job = await sync_service.get_job(job_id, tenant_ctx.tenant_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Sync job not found")

    return SyncJobResponse(
        job_id=job.id,
        data_source_id=job.data_source_id,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        documents_found=job.documents_found,
        documents_processed=job.documents_processed,
        documents_failed=job.documents_failed,
        error_message=job.error_message,
    )


@router.post("/sync-jobs/{job_id}/cancel")
async def cancel_sync_job(
    job_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> dict[str, str]:
    """Cancel a running sync job.

    Args:
        job_id: Sync job ID to cancel
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client

    Returns:
        Confirmation message
    """
    logger.info(f"Cancelling sync job {job_id}")

    sync_service = SyncService(db, redis)

    try:
        await sync_service.cancel_job(job_id, tenant_ctx.tenant_id)
        return {"message": f"Sync job {job_id} cancellation requested"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
