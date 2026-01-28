from uuid import UUID
import time

from fastapi import APIRouter, Depends, HTTPException, Header, Query
import structlog

from aswa_query.config import Settings, get_settings
from aswa_query.models.query import InsightQueryRequest
from aswa_query.models.common import PaginatedResponse
from aswa_query.services.insight_client import InsightClient

router = APIRouter()
logger = structlog.get_logger()


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


@router.post("")
async def query_insights(
    request: InsightQueryRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    settings: Settings = Depends(get_settings),
) -> PaginatedResponse:
    """Query extracted insights.

    Returns insights matching the query criteria, optionally filtered
    by type, document, or confidence threshold.
    """
    try:
        client = InsightClient(settings.insight_engine_url)

        result = await client.query_insights(
            tenant_id=tenant_id,
            query=request.query,
            insight_types=request.insight_types,
            document_ids=request.document_ids,
            min_confidence=request.min_confidence,
            limit=request.limit,
            offset=request.offset,
        )

        return result

    except Exception as e:
        logger.error("Insight query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_insight_summary(
    tenant_id: UUID = Depends(get_tenant_id),
    document_id: UUID | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get a summary of extracted insights."""
    try:
        client = InsightClient(settings.insight_engine_url)
        return await client.get_summary(tenant_id, document_id)
    except Exception as e:
        logger.error("Summary fetch failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_insight_trends(
    tenant_id: UUID = Depends(get_tenant_id),
    days: int = Query(30, ge=1, le=365),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get insight trends over time."""
    try:
        client = InsightClient(settings.insight_engine_url)
        return await client.get_trends(tenant_id, days)
    except Exception as e:
        logger.error("Trends fetch failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
