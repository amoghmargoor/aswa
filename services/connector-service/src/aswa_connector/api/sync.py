"""Sync management endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

from aswa_connector.dependencies import DbSession, TenantCtx, Provider
from aswa_connector.framework.models import SyncJobStatus

logger = get_logger(__name__)

router = APIRouter()


class TriggerSyncRequest(BaseModel):
    """Request to trigger a sync."""
    full_refresh: bool = False


class SyncJobResponse(BaseModel):
    """Sync job response."""
    id: UUID
    connection_id: UUID
    status: str
    sync_mode: str = "incremental"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_synced: int = 0
    bytes_synced: int = 0
    error_message: str | None = None


class SyncJobListResponse(BaseModel):
    """Paginated sync job list."""
    content: list[SyncJobResponse]
    total_elements: int
    total_pages: int
    current_page: int
    page_size: int


@router.post("/connections/{connection_id}/sync", response_model=SyncJobResponse, status_code=202)
async def trigger_sync(
    connection_id: UUID,
    request: TriggerSyncRequest,
    tenant: TenantCtx,
    db: DbSession,
    provider: Provider,
) -> SyncJobResponse:
    """Trigger a sync for a connection."""
    from sqlalchemy import select
    from aswa_connector.models.connection import ConnectionModel
    from aswa_connector.models.sync_job import SyncJobModel

    query = select(ConnectionModel).where(
        ConnectionModel.id == connection_id,
        ConnectionModel.tenant_id == tenant["tenant_id"],
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if not connection.provider_connection_id:
        raise HTTPException(status_code=400, detail="Connection not configured")

    job = await provider.trigger_airbyte_sync(
        airbyte_connection_id=connection.provider_connection_id,
        our_connection_id=connection_id,
        tenant_id=tenant["tenant_id"],
        full_refresh=request.full_refresh,
    )

    db_job = SyncJobModel(
        id=job.id,
        connection_id=connection_id,
        tenant_id=tenant["tenant_id"],
        status=job.status.value,
        sync_mode=job.sync_mode,
        started_at=job.started_at,
        provider_job_id=job.provider_job_id,
    )
    db.add(db_job)
    await db.flush()

    return SyncJobResponse(
        id=job.id,
        connection_id=connection_id,
        status=job.status.value,
        sync_mode=job.sync_mode,
        started_at=job.started_at,
    )


@router.get("/sync-jobs", response_model=SyncJobListResponse)
async def list_sync_jobs(
    tenant: TenantCtx,
    db: DbSession,
    connection_id: UUID | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
) -> SyncJobListResponse:
    """List sync jobs."""
    from sqlalchemy import select, func
    from aswa_connector.models.sync_job import SyncJobModel

    query = select(SyncJobModel).where(SyncJobModel.tenant_id == tenant["tenant_id"])
    if connection_id:
        query = query.where(SyncJobModel.connection_id == connection_id)
    if status:
        query = query.where(SyncJobModel.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.offset(page * size).limit(size).order_by(SyncJobModel.started_at.desc())
    jobs = (await db.execute(query)).scalars().all()

    return SyncJobListResponse(
        content=[SyncJobResponse(
            id=j.id, connection_id=j.connection_id, status=j.status,
            sync_mode=j.sync_mode, started_at=j.started_at,
            completed_at=j.completed_at, records_synced=j.records_synced,
            bytes_synced=j.bytes_synced, error_message=j.error_message,
        ) for j in jobs],
        total_elements=total,
        total_pages=(total + size - 1) // size,
        current_page=page,
        page_size=size,
    )


@router.post("/sync-jobs/{job_id}/cancel", status_code=200)
async def cancel_sync_job(
    job_id: UUID,
    tenant: TenantCtx,
    db: DbSession,
    provider: Provider,
) -> dict[str, str]:
    """Cancel a running sync job."""
    from sqlalchemy import select
    from aswa_connector.models.sync_job import SyncJobModel

    query = select(SyncJobModel).where(
        SyncJobModel.id == job_id,
        SyncJobModel.tenant_id == tenant["tenant_id"],
    )
    job = (await db.execute(query)).scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job.status}")

    if job.provider_job_id:
        await provider.cancel_airbyte_job(int(job.provider_job_id))

    job.status = SyncJobStatus.CANCELLED.value
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"message": "Job cancelled"}
