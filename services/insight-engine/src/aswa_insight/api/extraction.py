"""Extraction API endpoints."""

from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

logger = structlog.get_logger()

router = APIRouter()


class TenantContext(BaseModel):
    """Tenant context from request headers."""

    tenant_id: UUID
    user_id: UUID
    roles: list[str] = Field(default_factory=list)


async def get_tenant_context(
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
    x_roles: str = Header(default=""),
) -> TenantContext:
    """Extract tenant context from headers."""
    try:
        return TenantContext(
            tenant_id=UUID(x_tenant_id),
            user_id=UUID(x_user_id),
            roles=x_roles.split(",") if x_roles else [],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid tenant context: {e}")


class ExtractionRequest(BaseModel):
    """Request to extract insights from documents."""

    document_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    extraction_types: list[str] = Field(
        default=["entities", "risks", "opportunities"],
        description="Types of insights to extract",
    )
    force_reextract: bool = Field(
        default=False,
        description="Force re-extraction even if already processed",
    )
    priority: int = Field(default=0, ge=0, le=10, description="Job priority (0-10)")


class ExtractionResponse(BaseModel):
    """Response for extraction request."""

    job_id: UUID
    status: str
    documents_queued: int
    estimated_time_seconds: int | None = None


class ExtractionJobStatus(BaseModel):
    """Status of an extraction job."""

    job_id: UUID
    status: str  # queued, processing, completed, failed
    total_documents: int
    processed_documents: int
    successful_extractions: int
    failed_extractions: int
    progress_percent: float
    created_at: str
    updated_at: str
    completed_at: str | None = None
    error_message: str | None = None


class ExtractionResult(BaseModel):
    """Result of document extraction."""

    document_id: UUID
    status: str
    entities_extracted: int = 0
    risks_extracted: int = 0
    opportunities_extracted: int = 0
    patterns_extracted: int = 0
    processing_time_ms: int = 0
    error: str | None = None


@router.post("/extract", response_model=dict[str, Any])
async def extract_insights(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Trigger insight extraction for documents.

    Queues documents for LLM-based insight extraction and returns
    a job ID for tracking progress.
    """
    from aswa_insight.services.extraction_service import ExtractionService

    session_factory = http_request.app.state.session_factory
    llm_client = http_request.app.state.llm_client

    service = ExtractionService(session_factory, llm_client)

    job = await service.create_extraction_job(
        document_ids=request.document_ids,
        tenant_id=tenant_ctx.tenant_id,
        extraction_types=request.extraction_types,
        force_reextract=request.force_reextract,
        priority=request.priority,
    )

    # Run extraction in background
    background_tasks.add_task(service.run_extraction_job, job.id, tenant_ctx.tenant_id)

    # Estimate time based on document count
    estimated_time = len(request.document_ids) * 15  # ~15 seconds per doc

    return {
        "success": True,
        "data": ExtractionResponse(
            job_id=job.id,
            status="queued",
            documents_queued=len(request.document_ids),
            estimated_time_seconds=estimated_time,
        ).model_dump(),
    }


@router.get("/extract/{job_id}/status", response_model=dict[str, Any])
async def get_extraction_status(
    job_id: UUID,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get extraction job status."""
    from aswa_insight.services.extraction_service import ExtractionService

    session_factory = http_request.app.state.session_factory
    llm_client = http_request.app.state.llm_client

    service = ExtractionService(session_factory, llm_client)
    status = await service.get_job_status(job_id, tenant_ctx.tenant_id)

    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"success": True, "data": status}


@router.get("/extract/{job_id}/results", response_model=dict[str, Any])
async def get_extraction_results(
    job_id: UUID,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get extraction job results."""
    from aswa_insight.services.extraction_service import ExtractionService

    session_factory = http_request.app.state.session_factory
    llm_client = http_request.app.state.llm_client

    service = ExtractionService(session_factory, llm_client)
    results = await service.get_job_results(job_id, tenant_ctx.tenant_id)

    if results is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"success": True, "data": results}


@router.post("/extract/{job_id}/cancel", response_model=dict[str, Any])
async def cancel_extraction(
    job_id: UUID,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Cancel an extraction job."""
    from aswa_insight.services.extraction_service import ExtractionService

    session_factory = http_request.app.state.session_factory
    llm_client = http_request.app.state.llm_client

    service = ExtractionService(session_factory, llm_client)
    success = await service.cancel_job(job_id, tenant_ctx.tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already completed")

    return {"success": True, "data": {"status": "cancelled"}}
