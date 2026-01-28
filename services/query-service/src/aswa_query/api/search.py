from uuid import UUID
import time

from fastapi import APIRouter, Depends, HTTPException, Header
import structlog

from aswa_query.config import Settings, get_settings
from aswa_query.models.query import SearchRequest, SearchResponse
from aswa_query.services.search_service import SearchService

router = APIRouter()
logger = structlog.get_logger()


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


@router.post("", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Perform semantic search across documents.

    Returns document chunks ranked by semantic similarity to the query.
    """
    start_time = time.time()

    try:
        search_service = SearchService(settings)

        results = await search_service.search(
            tenant_id=tenant_id,
            query=request.query,
            document_ids=request.document_ids,
            limit=request.limit,
            offset=request.offset,
            min_score=request.min_score,
        )

        processing_time = int((time.time() - start_time) * 1000)

        return SearchResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similar/{document_id}")
async def find_similar_documents(
    document_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    limit: int = 10,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """Find documents similar to the given document."""
    search_service = SearchService(settings)

    try:
        return await search_service.find_similar(
            tenant_id=tenant_id,
            document_id=document_id,
            limit=limit,
        )
    except Exception as e:
        logger.error("Similar search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
