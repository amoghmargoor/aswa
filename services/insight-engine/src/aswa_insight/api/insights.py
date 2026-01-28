"""Insights API endpoints."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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


class Insight(BaseModel):
    """Insight model."""

    id: UUID
    tenant_id: UUID
    insight_type: str  # entity, risk, opportunity, pattern
    category: str
    title: str
    description: str
    confidence: float
    severity: str | None = None  # for risks
    impact: str | None = None  # for opportunities
    source_documents: list[UUID]
    source_chunks: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime


class InsightSummary(BaseModel):
    """Summary statistics for insights."""

    total_insights: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    avg_confidence: float
    new_today: int
    new_this_week: int
    confirmed_count: int
    rejected_count: int


class FeedbackRequest(BaseModel):
    """Request to submit feedback on an insight."""

    feedback: Literal["confirmed", "rejected"]
    comment: str | None = None


class PageResponse(BaseModel):
    """Paginated response."""

    content: list[Insight]
    page: int
    size: int
    total_elements: int
    total_pages: int


@router.get("/insights", response_model=dict[str, Any])
async def list_insights(
    http_request: Request,
    insight_type: Literal["entity", "risk", "opportunity", "pattern", "all"] = "all",
    category: str | None = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    status: str = "active",
    source_document_id: UUID | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """List insights with filtering and pagination."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    result = await service.list_insights(
        tenant_id=tenant_ctx.tenant_id,
        insight_type=insight_type if insight_type != "all" else None,
        category=category,
        min_confidence=min_confidence,
        status=status,
        source_document_id=source_document_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        size=size,
    )

    return {"success": True, "data": result}


@router.get("/insights/summary", response_model=dict[str, Any])
async def get_insights_summary(
    http_request: Request,
    days: int = Query(7, ge=1, le=90),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get summary statistics of insights."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    summary = await service.get_summary(tenant_ctx.tenant_id, days)

    return {"success": True, "data": summary}


@router.get("/insights/{insight_id}", response_model=dict[str, Any])
async def get_insight(
    insight_id: UUID,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get insight by ID."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    insight = await service.get_insight(insight_id, tenant_ctx.tenant_id)

    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {"success": True, "data": insight}


@router.post("/insights/{insight_id}/feedback", response_model=dict[str, Any])
async def submit_feedback(
    insight_id: UUID,
    feedback_request: FeedbackRequest,
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Submit user feedback on an insight."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    success = await service.update_feedback(
        insight_id=insight_id,
        tenant_id=tenant_ctx.tenant_id,
        user_id=tenant_ctx.user_id,
        feedback=feedback_request.feedback,
        comment=feedback_request.comment,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {"success": True, "data": {"status": "feedback_recorded"}}


@router.patch("/insights/{insight_id}/status", response_model=dict[str, Any])
async def update_insight_status(
    insight_id: UUID,
    status: Literal["active", "archived", "dismissed"],
    http_request: Request,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Update insight status."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    success = await service.update_status(
        insight_id=insight_id,
        tenant_id=tenant_ctx.tenant_id,
        status=status,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {"success": True, "data": {"status": status}}


@router.get("/insights/related/{insight_id}", response_model=dict[str, Any])
async def get_related_insights(
    insight_id: UUID,
    http_request: Request,
    limit: int = Query(10, ge=1, le=50),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get insights related to a specific insight."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    related = await service.get_related_insights(
        insight_id=insight_id,
        tenant_id=tenant_ctx.tenant_id,
        limit=limit,
    )

    return {"success": True, "data": related}


@router.get("/insights/trends", response_model=dict[str, Any])
async def get_insight_trends(
    http_request: Request,
    days: int = Query(30, ge=7, le=90),
    insight_type: str | None = None,
    tenant_ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Get insight trends over time."""
    from aswa_insight.services.insight_service import InsightService

    session_factory = http_request.app.state.session_factory
    service = InsightService(session_factory)

    trends = await service.get_trends(
        tenant_id=tenant_ctx.tenant_id,
        days=days,
        insight_type=insight_type,
    )

    return {"success": True, "data": trends}
