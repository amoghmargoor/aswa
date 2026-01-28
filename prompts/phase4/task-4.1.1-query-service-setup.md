# Task 4.1.1: Query Service Structure & API Endpoints

## Context

You are building the ASWA query-service, a Python FastAPI service that handles natural language queries against ingested documents and extracted insights. This service will be the main interface for users to ask questions and receive AI-generated answers with citations.

The service should be created at `/services/query-service/` following the same patterns as the insight-engine service at `/services/insight-engine/`.

## Objective

Create the query service with:
1. FastAPI application structure with async support
2. RESTful API endpoints for queries
3. Health checks and metrics endpoints
4. Request/response models with validation
5. Middleware for logging, CORS, and tenant isolation

## Requirements

### 1. Create `/services/query-service/pyproject.toml`
```toml
[project]
name = "aswa-query-service"
version = "0.1.0"
description = "ASWA Query Service - Natural language queries and RAG"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
    "structlog>=24.1.0",
    "redis>=5.0.0",
    "qdrant-client>=1.7.0",
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
    "opentelemetry-instrumentation-fastapi>=0.43b0",
    "prometheus-client>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

### 2. Create `/services/query-service/src/aswa_query/__init__.py`
```python
"""ASWA Query Service - Natural language queries and RAG."""

__version__ = "0.1.0"
```

### 3. Create `/services/query-service/src/aswa_query/config.py`
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Query service configuration."""

    # Service
    service_name: str = "query-service"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8003
    workers: int = 4

    # API
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True

    # Redis Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600

    # Vector Store (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    # Insight Engine
    insight_engine_url: str = "http://localhost:8002"

    # LLM Settings
    llm_provider: str = "bedrock"  # bedrock, azure, openai
    llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.1

    # Query Settings
    max_context_chunks: int = 10
    min_relevance_score: float = 0.7
    max_query_length: int = 1000

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: list[str] = ["*"]

    class Config:
        env_prefix = "QUERY_"
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 4. Create `/services/query-service/src/aswa_query/models/__init__.py`
```python
from .query import QueryRequest, QueryResponse, QueryResult, Citation
from .common import HealthResponse, ErrorResponse, PaginatedResponse

__all__ = [
    "QueryRequest",
    "QueryResponse",
    "QueryResult",
    "Citation",
    "HealthResponse",
    "ErrorResponse",
    "PaginatedResponse",
]
```

### 5. Create `/services/query-service/src/aswa_query/models/query.py`
```python
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class QueryType(str, Enum):
    """Type of query."""
    SEARCH = "search"
    QUESTION = "question"
    SUMMARY = "summary"
    INSIGHTS = "insights"


class Citation(BaseModel):
    """A citation/source reference."""
    document_id: UUID
    document_name: str
    chunk_id: str | None = None
    page_number: int | None = None
    relevance_score: float
    excerpt: str = Field(..., max_length=500)


class QueryRequest(BaseModel):
    """Request to query the system."""
    query: str = Field(..., min_length=1, max_length=1000)
    query_type: QueryType = QueryType.QUESTION
    document_ids: list[UUID] | None = Field(None, description="Filter to specific documents")
    include_insights: bool = Field(True, description="Include extracted insights")
    include_raw_content: bool = Field(False, description="Include raw document content")
    max_results: int = Field(10, ge=1, le=50)
    min_relevance: float = Field(0.7, ge=0, le=1)

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        return v.strip()


class QueryResult(BaseModel):
    """A single query result."""
    id: UUID = Field(default_factory=uuid4)
    content: str
    content_type: str  # "insight", "document_chunk", "summary"
    relevance_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Response to a query."""
    query_id: UUID = Field(default_factory=uuid4)
    query: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    results: list[QueryResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    processing_time_ms: int
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchRequest(BaseModel):
    """Request for semantic search."""
    query: str = Field(..., min_length=1, max_length=500)
    document_ids: list[UUID] | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    min_score: float = Field(0.5, ge=0, le=1)


class SearchResult(BaseModel):
    """A search result."""
    document_id: UUID
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response to a search request."""
    query: str
    results: list[SearchResult]
    total_results: int
    processing_time_ms: int


class InsightQueryRequest(BaseModel):
    """Request to query insights."""
    query: str | None = Field(None, max_length=500)
    insight_types: list[str] | None = None
    document_ids: list[UUID] | None = None
    min_confidence: float = Field(0.5, ge=0, le=1)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
```

### 6. Create `/services/query-service/src/aswa_query/models/common.py`
```python
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    service: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dependencies: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: dict[str, Any] | None = None
    request_id: UUID | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def create(cls, items: list[T], total: int, limit: int, offset: int) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total,
        )
```

### 7. Create `/services/query-service/src/aswa_query/api/__init__.py`
```python
from fastapi import APIRouter

from .health import router as health_router
from .query import router as query_router
from .search import router as search_router
from .insights import router as insights_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(query_router, prefix="/query", tags=["query"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(insights_router, prefix="/insights", tags=["insights"])
```

### 8. Create `/services/query-service/src/aswa_query/api/health.py`
```python
from fastapi import APIRouter, Depends
import structlog

from aswa_query import __version__
from aswa_query.config import Settings, get_settings
from aswa_query.models import HealthResponse

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Health check endpoint."""
    dependencies = {}

    # Check Redis
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url)
        await client.ping()
        dependencies["redis"] = "healthy"
        await client.close()
    except Exception as e:
        dependencies["redis"] = f"unhealthy: {str(e)}"

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url)
        client.get_collections()
        dependencies["qdrant"] = "healthy"
    except Exception as e:
        dependencies["qdrant"] = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if all("healthy" == v for v in dependencies.values()) else "degraded",
        service=settings.service_name,
        version=__version__,
        dependencies=dependencies,
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness check for Kubernetes."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Liveness check for Kubernetes."""
    return {"alive": True}
```

### 9. Create `/services/query-service/src/aswa_query/api/query.py`
```python
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
```

### 10. Create `/services/query-service/src/aswa_query/api/search.py`
```python
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
```

### 11. Create `/services/query-service/src/aswa_query/api/insights.py`
```python
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
```

### 12. Create `/services/query-service/src/aswa_query/app.py`
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from aswa_query import __version__
from aswa_query.config import get_settings
from aswa_query.api import api_router
from aswa_query.middleware import (
    RequestLoggingMiddleware,
    TenantContextMiddleware,
    RateLimitMiddleware,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(
        "Starting query service",
        version=__version__,
        environment=settings.environment,
    )

    yield

    logger.info("Shutting down query service")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Query Service",
        description="Natural language queries and RAG for ASWA",
        version=__version__,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Routes
    app.include_router(api_router, prefix=settings.api_prefix)

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(exc)},
        )

    # OpenTelemetry instrumentation
    FastAPIInstrumentor.instrument_app(app)

    return app


app = create_app()
```

### 13. Create `/services/query-service/src/aswa_query/middleware.py`
```python
import time
from typing import Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from aswa_query.config import get_settings

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid4())
        start_time = time.time()

        # Add request ID to state
        request.state.request_id = request_id

        # Log request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        # Log response
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Request completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = str(duration_ms)

        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract and validate tenant context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            try:
                request.state.tenant_id = UUID(tenant_id)
            except ValueError:
                pass

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""

    def __init__(self, app):
        super().__init__(app)
        self._request_counts: dict[str, list[float]] = {}
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/live"]:
            return await call_next(request)

        # Get client identifier
        client_id = request.headers.get("X-Tenant-ID", request.client.host if request.client else "unknown")

        # Check rate limit
        now = time.time()
        window_start = now - self.settings.rate_limit_window_seconds

        if client_id not in self._request_counts:
            self._request_counts[client_id] = []

        # Clean old requests
        self._request_counts[client_id] = [
            t for t in self._request_counts[client_id] if t > window_start
        ]

        if len(self._request_counts[client_id]) >= self.settings.rate_limit_requests:
            return Response(
                content='{"error": "rate_limit_exceeded", "message": "Too many requests"}',
                status_code=429,
                media_type="application/json",
            )

        self._request_counts[client_id].append(now)

        return await call_next(request)
```

### 14. Create `/services/query-service/src/aswa_query/services/__init__.py`
```python
from .query_service import QueryService
from .search_service import SearchService
from .cache import CacheService

__all__ = ["QueryService", "SearchService", "CacheService"]
```

### 15. Create `/services/query-service/src/aswa_query/services/cache.py`
```python
from typing import Any
from uuid import UUID
import json

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class CacheService:
    """Redis-based caching service."""

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        try:
            client = await self._get_client()
            await client.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(value, default=str),
            )
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def get_query_result(self, query_id: UUID) -> dict | None:
        """Get cached query result."""
        return await self.get(f"query:{query_id}")

    async def set_query_result(self, query_id: UUID, result: dict, ttl: int | None = None) -> bool:
        """Cache query result."""
        return await self.set(f"query:{query_id}", result, ttl)

    async def get_query_cache(self, tenant_id: UUID, query_hash: str) -> dict | None:
        """Get cached response for a query."""
        return await self.get(f"cache:{tenant_id}:{query_hash}")

    async def set_query_cache(self, tenant_id: UUID, query_hash: str, result: dict, ttl: int | None = None) -> bool:
        """Cache query response."""
        return await self.set(f"cache:{tenant_id}:{query_hash}", result, ttl)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
```

### 16. Create stub service files

Create `/services/query-service/src/aswa_query/services/query_service.py`:
```python
from uuid import UUID
import hashlib

import structlog

from aswa_query.config import Settings
from aswa_query.models.query import QueryRequest, QueryResponse, QueryResult
from .cache import CacheService

logger = structlog.get_logger()


class QueryService:
    """Service for processing natural language queries."""

    def __init__(self, settings: Settings, cache: CacheService):
        self.settings = settings
        self.cache = cache

    async def process_query(
        self,
        tenant_id: UUID,
        request: QueryRequest,
    ) -> QueryResponse:
        """Process a query request.

        This is a stub implementation. Full implementation in Task 4.2.2.
        """
        # Check cache
        query_hash = self._hash_query(request)
        cached = await self.cache.get_query_cache(tenant_id, query_hash)
        if cached:
            response = QueryResponse(**cached)
            response.cached = True
            return response

        # TODO: Implement full query processing in Task 4.2
        response = QueryResponse(
            query=request.query,
            answer="Query processing not yet implemented. See Task 4.2.",
            confidence=0.0,
            results=[],
            citations=[],
            processing_time_ms=0,
        )

        return response

    def _hash_query(self, request: QueryRequest) -> str:
        """Generate hash for query caching."""
        content = f"{request.query}:{request.query_type}:{request.document_ids}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

Create `/services/query-service/src/aswa_query/services/search_service.py`:
```python
from uuid import UUID
from typing import Any

import structlog
from qdrant_client import QdrantClient

from aswa_query.config import Settings
from aswa_query.models.query import SearchResult

logger = structlog.get_logger()


class SearchService:
    """Service for semantic search."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self.settings.qdrant_url)
        return self._client

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        document_ids: list[UUID] | None = None,
        limit: int = 20,
        offset: int = 0,
        min_score: float = 0.5,
    ) -> list[SearchResult]:
        """Perform semantic search.

        This is a stub implementation. Full implementation in Task 4.2.1.
        """
        # TODO: Implement full search in Task 4.2.1
        logger.info("Search stub called", query=query, tenant_id=str(tenant_id))
        return []

    async def find_similar(
        self,
        tenant_id: UUID,
        document_id: UUID,
        limit: int = 10,
    ) -> list[dict]:
        """Find similar documents.

        This is a stub implementation. Full implementation in Task 4.2.1.
        """
        # TODO: Implement in Task 4.2.1
        return []
```

Create `/services/query-service/src/aswa_query/services/insight_client.py`:
```python
from uuid import UUID
from typing import Any

import httpx
import structlog

from aswa_query.models.common import PaginatedResponse

logger = structlog.get_logger()


class InsightClient:
    """Client for the insight-engine service."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def query_insights(
        self,
        tenant_id: UUID,
        query: str | None = None,
        insight_types: list[str] | None = None,
        document_ids: list[UUID] | None = None,
        min_confidence: float = 0.5,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedResponse:
        """Query insights from insight-engine."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/insights/query",
                headers={"X-Tenant-ID": str(tenant_id)},
                json={
                    "query": query,
                    "insight_types": insight_types,
                    "document_ids": [str(d) for d in document_ids] if document_ids else None,
                    "min_confidence": min_confidence,
                    "limit": limit,
                    "offset": offset,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return PaginatedResponse(
                items=data.get("items", []),
                total=data.get("total", 0),
                limit=limit,
                offset=offset,
                has_more=data.get("has_more", False),
            )

    async def get_summary(self, tenant_id: UUID, document_id: UUID | None = None) -> dict:
        """Get insight summary."""
        async with httpx.AsyncClient() as client:
            params = {}
            if document_id:
                params["document_id"] = str(document_id)

            response = await client.get(
                f"{self.base_url}/api/v1/insights/summary",
                headers={"X-Tenant-ID": str(tenant_id)},
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_trends(self, tenant_id: UUID, days: int = 30) -> dict:
        """Get insight trends."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/insights/trends",
                headers={"X-Tenant-ID": str(tenant_id)},
                params={"days": days},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
```

## Test Requirements

### Create `/services/query-service/tests/__init__.py`

### Create `/services/query-service/tests/conftest.py`
```python
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from aswa_query.app import app
from aswa_query.config import Settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def headers(tenant_id):
    return {"X-Tenant-ID": str(tenant_id)}


@pytest.fixture
def settings():
    return Settings()
```

### Create `/services/query-service/tests/test_api.py`
```python
import pytest
from uuid import uuid4


class TestHealthEndpoints:
    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_readiness(self, client):
        """Test readiness endpoint."""
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_liveness(self, client):
        """Test liveness endpoint."""
        response = client.get("/api/v1/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestQueryEndpoints:
    def test_query_requires_tenant(self, client):
        """Test that query requires tenant ID."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test query"},
        )
        assert response.status_code == 422

    def test_query_with_tenant(self, client, headers):
        """Test query with tenant ID."""
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": "What are the main risks?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "query_id" in data
        assert "answer" in data

    def test_query_validation(self, client, headers):
        """Test query validation."""
        # Empty query
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": ""},
        )
        assert response.status_code == 422

        # Query too long
        response = client.post(
            "/api/v1/query",
            headers=headers,
            json={"query": "x" * 1001},
        )
        assert response.status_code == 422


class TestSearchEndpoints:
    def test_search(self, client, headers):
        """Test semantic search."""
        response = client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "test search"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "processing_time_ms" in data


class TestInsightEndpoints:
    def test_query_insights(self, client, headers):
        """Test insight query."""
        response = client.post(
            "/api/v1/insights",
            headers=headers,
            json={"min_confidence": 0.5},
        )
        # May fail due to insight-engine not running, which is OK
        assert response.status_code in [200, 500]
```

### Create `/services/query-service/tests/test_models.py`
```python
import pytest
from uuid import uuid4

from aswa_query.models.query import (
    QueryRequest,
    QueryResponse,
    QueryType,
    Citation,
    SearchRequest,
)


class TestQueryRequest:
    def test_valid_request(self):
        """Test valid query request."""
        request = QueryRequest(query="What are the risks?")
        assert request.query_type == QueryType.QUESTION
        assert request.max_results == 10

    def test_query_stripping(self):
        """Test query is stripped."""
        request = QueryRequest(query="  test query  ")
        assert request.query == "test query"

    def test_query_type_override(self):
        """Test query type override."""
        request = QueryRequest(query="test", query_type=QueryType.SUMMARY)
        assert request.query_type == QueryType.SUMMARY


class TestQueryResponse:
    def test_response_creation(self):
        """Test response creation."""
        response = QueryResponse(
            query="test",
            answer="answer",
            confidence=0.9,
            processing_time_ms=100,
        )
        assert response.query_id is not None
        assert response.confidence == 0.9


class TestCitation:
    def test_citation_creation(self):
        """Test citation creation."""
        citation = Citation(
            document_id=uuid4(),
            document_name="test.pdf",
            relevance_score=0.85,
            excerpt="Test excerpt",
        )
        assert citation.relevance_score == 0.85
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/ -v`
2. Verify imports: `python -c "from aswa_query.app import app"`
3. Start service: `uvicorn aswa_query.app:app --reload`
4. Test endpoints: `curl http://localhost:8003/api/v1/health`
