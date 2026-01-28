from datetime import datetime
from typing import Any
from uuid import UUID
import time

from fastapi import APIRouter, Depends, HTTPException, Header, Query
import structlog

from aswa_query.config import Settings, get_settings
from aswa_query.models.query import (
    QueryRequest,
    QueryResponse,
    QueryType,
)
from aswa_query.services.query_service import QueryService
from aswa_query.services.cache import CacheService

router = APIRouter()
logger = structlog.get_logger()


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    """Submit a natural language query.

    This endpoint accepts natural language queries and returns AI-generated
    answers with citations from relevant documents and insights.
    """
    start_time = time.time()

    logger.info(
        "Query received",
        tenant_id=str(tenant_id),
        query_type=request.query_type,
        query_length=len(request.query),
    )

    try:
        # Initialize services
        cache_service = CacheService(settings.redis_url)
        query_service = QueryService(settings, cache_service)

        # Process query
        response = await query_service.process_query(
            tenant_id=tenant_id,
            request=request,
        )

        processing_time = int((time.time() - start_time) * 1000)
        response.processing_time_ms = processing_time

        logger.info(
            "Query processed",
            query_id=str(response.query_id),
            processing_time_ms=processing_time,
            result_count=len(response.results),
            cached=response.cached,
        )

        return response

    except Exception as e:
        logger.error("Query failed", error=str(e), tenant_id=str(tenant_id))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query_result(
    query_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    """Get a previously submitted query result."""
    cache_service = CacheService(settings.redis_url)

    result = await cache_service.get_query_result(query_id)
    if not result:
        raise HTTPException(status_code=404, detail="Query result not found")

    # Verify tenant isolation
    if result.get("tenant_id") != str(tenant_id):
        raise HTTPException(status_code=404, detail="Query result not found")

    return QueryResponse(**result)


@router.post("/batch")
async def submit_batch_queries(
    queries: list[QueryRequest],
    tenant_id: UUID = Depends(get_tenant_id),
    settings: Settings = Depends(get_settings),
) -> list[QueryResponse]:
    """Submit multiple queries in batch."""
    if len(queries) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 queries per batch")

    cache_service = CacheService(settings.redis_url)
    query_service = QueryService(settings, cache_service)

    responses = []
    for request in queries:
        try:
            response = await query_service.process_query(tenant_id, request)
            responses.append(response)
        except Exception as e:
            logger.error("Batch query failed", error=str(e))
            # Continue processing other queries

    return responses
