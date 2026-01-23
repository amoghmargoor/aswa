# Task 3.1.1: Insight Engine Service Setup

## Subtask: Create Insight Engine Service Structure

**Claude Code Prompt:**
```
Create the Python insight engine service at /services/insight-engine/.

1. /services/insight-engine/pyproject.toml:
[tool.poetry]
name = "aswa-insight-engine"
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11,<3.13"
aswa-common = { path = "../../libs/common-python", develop = true }
fastapi = ">=0.109"
uvicorn = { extras = ["standard"], version = ">=0.27" }
instructor = ">=1.0"
openai = ">=1.10"
aioboto3 = ">=12.0"
pydantic = ">=2.6"
structlog = ">=24.1"
redis = ">=5.0"
httpx = ">=0.26"

[tool.poetry.group.dev.dependencies]
pytest = ">=8.0"
pytest-asyncio = ">=0.23"
pytest-cov = ">=4.1"
respx = ">=0.20"

2. /services/insight-engine/src/aswa_insight/__init__.py

3. /services/insight-engine/src/aswa_insight/config.py:
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class InsightSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INSIGHT_")
    
    service_name: str = "aswa-insight-engine"
    
    # LLM Configuration
    llm_provider: Literal["bedrock", "azure_openai"] = "bedrock"
    
    # Bedrock settings
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # Azure OpenAI settings
    azure_endpoint: str | None = None
    azure_api_key: str | None = None
    azure_deployment: str = "gpt-4o"
    azure_api_version: str = "2024-02-01"
    
    # Extraction settings
    max_tokens: int = 4096
    temperature: float = 0.0
    extraction_timeout_seconds: int = 120
    max_retries: int = 3
    
    # Batch settings
    batch_size: int = 10
    concurrent_extractions: int = 5
    
    # Confidence thresholds
    min_entity_confidence: float = 0.6
    min_insight_confidence: float = 0.5

class Settings:
    insight: InsightSettings = InsightSettings()

settings = Settings()

4. /services/insight-engine/src/aswa_insight/main.py:
from fastapi import FastAPI
from contextlib import asynccontextmanager
from aswa_common.logging import configure_logging
from aswa_common.metrics import MetricsRegistry
from prometheus_client import make_asgi_app
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging(settings.insight.service_name, json_output=True)
    logger.info("Starting Insight Engine service")
    
    # Initialize LLM client
    from .llm import get_llm_client
    app.state.llm_client = await get_llm_client()
    
    # Initialize database
    from aswa_common.db import create_engine, AsyncSessionFactory
    from aswa_common.config import DatabaseSettings
    db_settings = DatabaseSettings()
    engine = create_engine(db_settings.async_url)
    app.state.session_factory = AsyncSessionFactory(engine)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Insight Engine service")
    await engine.dispose()

app = FastAPI(
    title="ASWA Insight Engine",
    version="0.1.0",
    lifespan=lifespan
)

# Mount metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
from .api import health, extraction, insights
app.include_router(health.router, tags=["health"])
app.include_router(extraction.router, prefix="/api/v1", tags=["extraction"])
app.include_router(insights.router, prefix="/api/v1", tags=["insights"])

# Exception handlers
from aswa_common.exceptions import AswaError
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AswaError)
async def aswa_exception_handler(request: Request, exc: AswaError):
    return JSONResponse(
        status_code=exc.code.http_status,
        content=exc.to_api_response()
    )

5. /services/insight-engine/src/aswa_insight/api/__init__.py

6. /services/insight-engine/src/aswa_insight/api/health.py:
from fastapi import APIRouter, Depends
from aswa_common.models import ApiResponse

router = APIRouter()

@router.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "insight-engine"}

@router.get("/ready")
async def ready() -> dict:
    # Check LLM connectivity
    # Check database connectivity
    return {"status": "ready"}

7. /services/insight-engine/src/aswa_insight/api/extraction.py:
from fastapi import APIRouter, Depends, BackgroundTasks
from uuid import UUID
from pydantic import BaseModel
from aswa_common.models import ApiResponse, TenantContext

router = APIRouter()

class ExtractionRequest(BaseModel):
    document_ids: list[UUID]
    extraction_types: list[str] = ["entities", "risks", "opportunities"]
    force_reextract: bool = False

class ExtractionResponse(BaseModel):
    job_id: UUID
    status: str
    documents_queued: int

@router.post("/extract", response_model=ApiResponse[ExtractionResponse])
async def extract_insights(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """Trigger insight extraction for documents."""
    from ..services.extraction_service import ExtractionService
    
    service = ExtractionService()
    job = await service.create_extraction_job(
        document_ids=request.document_ids,
        tenant_id=tenant_ctx.tenant_id,
        extraction_types=request.extraction_types,
        force_reextract=request.force_reextract
    )
    
    # Run extraction in background
    background_tasks.add_task(service.run_extraction_job, job.id)
    
    return ApiResponse.ok(ExtractionResponse(
        job_id=job.id,
        status="queued",
        documents_queued=len(request.document_ids)
    ))

@router.get("/extract/{job_id}/status")
async def get_extraction_status(
    job_id: UUID,
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """Get extraction job status."""
    from ..services.extraction_service import ExtractionService
    
    service = ExtractionService()
    status = await service.get_job_status(job_id, tenant_ctx.tenant_id)
    return ApiResponse.ok(status)

8. /services/insight-engine/src/aswa_insight/api/insights.py:
from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Literal
from aswa_common.models import ApiResponse, PageRequest, PageResponse, TenantContext

router = APIRouter()

@router.get("/insights")
async def list_insights(
    insight_type: Literal["entity", "risk", "opportunity", "pattern", "all"] = "all",
    category: str | None = None,
    min_confidence: float = 0.0,
    status: str = "active",
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """List insights with filtering."""
    from ..services.insight_service import InsightService
    
    service = InsightService()
    result = await service.list_insights(
        tenant_id=tenant_ctx.tenant_id,
        insight_type=insight_type if insight_type != "all" else None,
        category=category,
        min_confidence=min_confidence,
        status=status,
        page=PageRequest(page=page, size=size)
    )
    return ApiResponse.ok(result)

@router.get("/insights/{insight_id}")
async def get_insight(
    insight_id: UUID,
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """Get insight by ID."""
    from ..services.insight_service import InsightService
    
    service = InsightService()
    insight = await service.get_insight(insight_id, tenant_ctx.tenant_id)
    return ApiResponse.ok(insight)

@router.post("/insights/{insight_id}/feedback")
async def submit_feedback(
    insight_id: UUID,
    feedback: Literal["confirmed", "rejected"],
    comment: str | None = None,
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """Submit user feedback on an insight."""
    from ..services.insight_service import InsightService
    
    service = InsightService()
    await service.update_feedback(
        insight_id=insight_id,
        tenant_id=tenant_ctx.tenant_id,
        user_id=tenant_ctx.user_id,
        feedback=feedback,
        comment=comment
    )
    return ApiResponse.ok({"status": "feedback_recorded"})

@router.get("/insights/summary")
async def get_insights_summary(
    days: int = Query(7, ge=1, le=90),
    tenant_ctx: TenantContext = Depends(get_tenant_context)
):
    """Get summary statistics of insights."""
    from ..services.insight_service import InsightService
    
    service = InsightService()
    summary = await service.get_summary(tenant_ctx.tenant_id, days)
    return ApiResponse.ok(summary)

9. /services/insight-engine/src/aswa_insight/llm/__init__.py:
from .client import get_llm_client, LLMClient
from .bedrock import BedrockClient
from .azure import AzureOpenAIClient

10. /services/insight-engine/tests/:
- conftest.py with fixtures for LLM mocking
- test_main.py - test app startup
- test_api_health.py
- test_api_extraction.py
- test_api_insights.py

Create comprehensive tests with mocked LLM responses.
Use pytest-asyncio for all async tests.
```