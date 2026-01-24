"""Webhook endpoints for Airbyte."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger
from aswa_connector.config import settings

logger = get_logger(__name__)
router = APIRouter()


class AirbyteWebhookPayload(BaseModel):
    """Airbyte webhook payload."""
    type: str
    connection_id: str
    workspace_id: str
    job_id: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AirbyteRecordBatch(BaseModel):
    """Batch of Airbyte records."""
    connection_id: str
    records: list[dict[str, Any]]


@router.post("/airbyte/webhook")
async def airbyte_webhook(
    payload: AirbyteWebhookPayload,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Handle Airbyte webhook events."""
    logger.info(f"Airbyte webhook: type={payload.type}, connection={payload.connection_id}")
    background_tasks.add_task(process_webhook, payload)
    return {"status": "accepted"}


async def process_webhook(payload: AirbyteWebhookPayload) -> None:
    """Process webhook in background."""
    from aswa_connector.dependencies import _session_factory
    from aswa_connector.models.sync_job import SyncJobModel
    from aswa_connector.models.connection import ConnectionModel
    from sqlalchemy import select

    if not _session_factory:
        return

    async with _session_factory() as db:
        try:
            conn = (await db.execute(
                select(ConnectionModel).where(
                    ConnectionModel.provider_connection_id == payload.connection_id
                )
            )).scalar_one_or_none()

            if not conn:
                return

            job = (await db.execute(
                select(SyncJobModel)
                .where(SyncJobModel.connection_id == conn.id)
                .order_by(SyncJobModel.started_at.desc())
                .limit(1)
            )).scalar_one_or_none()

            if job:
                if payload.type == "connection.succeeded":
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    conn.last_sync_at = job.completed_at
                elif payload.type == "connection.failed":
                    job.status = "failed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = payload.data.get("failure_reason")

            await db.commit()
        except Exception as e:
            logger.exception(f"Webhook processing failed: {e}")


@router.post("/airbyte/records")
async def receive_records(
    batch: AirbyteRecordBatch,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Receive records from Airbyte destination."""
    logger.info(f"Received {len(batch.records)} records from {batch.connection_id}")
    background_tasks.add_task(forward_to_ingestion, batch)
    return {"status": "accepted", "count": len(batch.records)}


async def forward_to_ingestion(batch: AirbyteRecordBatch) -> None:
    """Forward records to ingestion service."""
    import httpx
    from aswa_connector.dependencies import _session_factory
    from aswa_connector.models.connection import ConnectionModel
    from sqlalchemy import select

    if not _session_factory:
        return

    async with _session_factory() as db:
        conn = (await db.execute(
            select(ConnectionModel).where(
                ConnectionModel.provider_connection_id == batch.connection_id
            )
        )).scalar_one_or_none()

        if not conn:
            return

        async with httpx.AsyncClient(timeout=30.0) as client:
            for record in batch.records:
                try:
                    await client.post(
                        f"{settings.connector.ingestion_service_url}/internal/documents/ingest",
                        json={
                            "tenant_id": str(conn.tenant_id),
                            "data_source_id": str(conn.id),
                            "external_id": record.get("id"),
                            "title": record.get("title", "Untitled"),
                            "content": record.get("content", str(record)),
                            "content_type": record.get("mime_type", "text/plain"),
                            "metadata": {"source": conn.connector_type},
                        },
                        headers={"X-Tenant-Id": str(conn.tenant_id)},
                    )
                except Exception as e:
                    logger.error(f"Failed to forward record: {e}")
