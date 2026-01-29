# Task 9.1.1: Agent Service Setup

## Objective

Create the foundational Agent Service that will power the AI agent platform. This service handles agent lifecycle management, execution orchestration, and integration with existing ASWA services.

## Prerequisites

- Phase 3-8 completed (insight-service, query-service, integration-service exist)
- PostgreSQL database running
- Redis for task queues
- Docker and Kubernetes infrastructure ready

## Language Choice: Python

**Rationale:**
- Consistency with existing ASWA Python services (ingestion, query, insight, notification)
- Better LLM library ecosystem (langchain, anthropic, openai SDKs)
- Faster iteration for AI-heavy features
- Reuse of common-python library patterns

## Directory Structure

```
services/agent-service/
├── src/
│   └── aswa_agents/
│       ├── __init__.py
│       ├── main.py                 # FastAPI application entry
│       ├── config.py               # Configuration management
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py           # API route definitions
│       │   ├── dependencies.py     # FastAPI dependencies
│       │   └── schemas.py          # Pydantic request/response models
│       ├── core/
│       │   ├── __init__.py
│       │   ├── base.py             # Base classes (Task 9.1.2)
│       │   ├── registry.py         # Agent registry (Task 9.1.3)
│       │   └── orchestrator.py     # Orchestrator (Task 9.1.4)
│       ├── agents/
│       │   ├── __init__.py
│       │   └── builtin/            # Built-in agents
│       ├── actions/
│       │   ├── __init__.py
│       │   └── blocks/             # Action blocks (Phase 9.4)
│       ├── generation/
│       │   ├── __init__.py
│       │   └── nlp/                # NLP generation (Phase 9.2)
│       ├── approval/
│       │   ├── __init__.py
│       │   └── service.py          # Approval workflows (Phase 9.6)
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── models.py           # SQLAlchemy models
│       │   └── repository.py       # Data access layer
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── base.py             # Connector interface
│       │   └── registry.py         # Connector registry
│       └── utils/
│           ├── __init__.py
│           └── metrics.py          # Prometheus metrics
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── unit/
│   │   └── ...
│   └── integration/
│       └── ...
├── alembic/
│   └── versions/                   # Database migrations
├── Dockerfile
├── pyproject.toml
├── alembic.ini
└── README.md
```

## Implementation

### Step 1: Create pyproject.toml

```toml
# services/agent-service/pyproject.toml
[project]
name = "aswa-agent-service"
version = "0.1.0"
description = "ASWA AI Agent Platform Service"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis>=5.0.0",
    "httpx>=0.26.0",
    "python-jose[cryptography]>=3.3.0",
    "pyyaml>=6.0.1",
    "jinja2>=3.1.2",
    "prometheus-client>=0.19.0",
    "structlog>=24.1.0",
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
    "opentelemetry-instrumentation-fastapi>=0.43b0",
    "anthropic>=0.18.0",
    "openai>=1.10.0",
    "tenacity>=8.2.0",
    "croniter>=2.0.0",
    "aswa-common>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.26.0",
    "factory-boy>=3.3.0",
    "fakeredis>=2.20.0",
    "testcontainers>=3.7.0",
    "black>=24.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=aswa_agents --cov-report=term-missing"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### Step 2: Create Configuration

```python
# services/agent-service/src/aswa_agents/config.py
"""Configuration management for Agent Service."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service Configuration
    service_name: str = "agent-service"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8090
    workers: int = 4

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_agents"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis Configuration
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_prefix: str = "aswa:agents:"

    # Authentication
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Internal Service URLs (for K8s service discovery)
    insight_service_url: str = "http://insight-service:8080"
    query_service_url: str = "http://query-service:8080"
    integration_service_url: str = "http://integration-service:8080"
    notification_service_url: str = "http://notification-service:8080"
    api_gateway_url: str = "http://api-gateway:8080"

    # LLM Configuration
    llm_provider: Literal["anthropic", "openai", "bedrock", "azure"] = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    aws_region: str = "us-east-1"
    default_model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4096

    # Agent Execution
    max_concurrent_executions: int = 100
    execution_timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Approval Configuration
    default_approval_timeout_hours: int = 24
    high_risk_actions: list[str] = Field(
        default=["send_email", "create_ticket", "update_document", "call_webhook"]
    )

    # Observability
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    otlp_endpoint: str | None = None

    # Feature Flags
    enable_nlp_generation: bool = True
    enable_visual_builder: bool = True
    enable_marketplace: bool = False

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Step 3: Create Main Application

```python
# services/agent-service/src/aswa_agents/main.py
"""FastAPI application entry point for Agent Service."""

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from aswa_agents.config import get_settings
from aswa_agents.api.routes import router as api_router
from aswa_agents.persistence.database import init_database, close_database
from aswa_agents.connectors.registry import ConnectorRegistry
from aswa_agents.core.registry import AgentRegistry
from aswa_agents.actions.registry import ActionBlockRegistry
from aswa_agents.utils.logging import setup_logging
from aswa_agents.utils.tracing import setup_tracing


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Setup logging
    setup_logging(settings.log_level)
    logger.info("Starting Agent Service", environment=settings.environment)

    # Setup tracing if enabled
    if settings.enable_tracing:
        setup_tracing(settings)

    # Initialize database
    await init_database(settings)
    logger.info("Database initialized")

    # Initialize registries
    ConnectorRegistry.initialize()
    AgentRegistry.initialize()
    ActionBlockRegistry.initialize()
    logger.info("Registries initialized")

    yield

    # Cleanup
    await close_database()
    logger.info("Agent Service shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Agent Service",
        description="AI Agent Platform for creating and managing custom agents",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "agent-service"}

    @app.get("/ready")
    async def readiness_check():
        # TODO: Check database and Redis connectivity
        return {"status": "ready"}

    # Mount API routes
    app.include_router(api_router, prefix="/api/v1")

    # Mount Prometheus metrics
    if settings.enable_metrics:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

    return app


# Application instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aswa_agents.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )
```

### Step 4: Create Database Setup

```python
# services/agent-service/src/aswa_agents/persistence/database.py
"""Database connection and session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from aswa_agents.config import Settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


# Global engine and session factory
_engine = None
_async_session_factory = None


async def init_database(settings: Settings) -> None:
    """Initialize database connection."""
    global _engine, _async_session_factory

    _engine = create_async_engine(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.debug,
    )

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_database() -> None:
    """Close database connection."""
    global _engine
    if _engine:
        await _engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Step 5: Create Logging Utility

```python
# services/agent-service/src/aswa_agents/utils/logging.py
"""Structured logging configuration."""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if log_level != "DEBUG"
                else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
```

### Step 6: Create Metrics Utility

```python
# services/agent-service/src/aswa_agents/utils/metrics.py
"""Prometheus metrics for Agent Service."""

from prometheus_client import Counter, Histogram, Gauge


# Agent metrics
AGENTS_TOTAL = Gauge(
    "aswa_agents_total",
    "Total number of registered agents",
    ["tenant_id", "status"],
)

AGENT_EXECUTIONS_TOTAL = Counter(
    "aswa_agent_executions_total",
    "Total number of agent executions",
    ["tenant_id", "agent_name", "status"],
)

AGENT_EXECUTION_DURATION = Histogram(
    "aswa_agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["tenant_id", "agent_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# Action metrics
ACTION_EXECUTIONS_TOTAL = Counter(
    "aswa_action_executions_total",
    "Total number of action block executions",
    ["tenant_id", "action_type", "status"],
)

ACTION_EXECUTION_DURATION = Histogram(
    "aswa_action_execution_duration_seconds",
    "Action block execution duration in seconds",
    ["action_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Approval metrics
APPROVALS_PENDING = Gauge(
    "aswa_approvals_pending",
    "Number of pending approval requests",
    ["tenant_id"],
)

APPROVALS_TOTAL = Counter(
    "aswa_approvals_total",
    "Total number of approval decisions",
    ["tenant_id", "decision"],
)

# NLP Generation metrics
NLP_GENERATIONS_TOTAL = Counter(
    "aswa_nlp_generations_total",
    "Total number of NLP agent generation requests",
    ["tenant_id", "status"],
)

NLP_GENERATION_DURATION = Histogram(
    "aswa_nlp_generation_duration_seconds",
    "NLP agent generation duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)
```

### Step 7: Create Base API Routes

```python
# services/agent-service/src/aswa_agents/api/routes.py
"""API route definitions for Agent Service."""

from fastapi import APIRouter

from aswa_agents.api.endpoints import (
    agents,
    executions,
    approvals,
    templates,
    actions,
    generation,
)


router = APIRouter()

# Include all endpoint routers
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(executions.router, prefix="/executions", tags=["executions"])
router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(actions.router, prefix="/actions", tags=["actions"])
router.include_router(generation.router, prefix="/generate", tags=["generation"])
```

```python
# services/agent-service/src/aswa_agents/api/endpoints/__init__.py
"""API endpoint modules."""
```

```python
# services/agent-service/src/aswa_agents/api/endpoints/agents.py
"""Agent management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.dependencies import get_current_tenant, get_db_session
from aswa_agents.api.schemas import (
    AgentCreate,
    AgentResponse,
    AgentListResponse,
    AgentUpdate,
    TriggerRequest,
    ExecutionResponse,
)
from aswa_agents.persistence.repository import AgentRepository


router = APIRouter()


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Create a new agent."""
    repo = AgentRepository(session)
    agent = await repo.create(tenant_id=tenant_id, data=agent_data)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentListResponse:
    """List all agents for tenant."""
    repo = AgentRepository(session)
    agents, total = await repo.list(
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Get agent by ID."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id=agent_id, tenant_id=tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Update an agent."""
    repo = AgentRepository(session)
    agent = await repo.update(
        agent_id=agent_id,
        tenant_id=tenant_id,
        data=agent_data,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete an agent."""
    repo = AgentRepository(session)
    deleted = await repo.delete(agent_id=agent_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/{agent_id}/trigger", response_model=ExecutionResponse)
async def trigger_agent(
    agent_id: UUID,
    trigger_data: TriggerRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionResponse:
    """Manually trigger an agent execution."""
    # Implementation in Task 9.1.4
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{agent_id}/test", response_model=ExecutionResponse)
async def test_agent(
    agent_id: UUID,
    trigger_data: TriggerRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionResponse:
    """Test agent with dry-run execution."""
    # Implementation in Task 9.5.1
    raise HTTPException(status_code=501, detail="Not implemented")
```

### Step 8: Create API Schemas

```python
# services/agent-service/src/aswa_agents/api/schemas.py
"""Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent status values."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class ApprovalMode(str, Enum):
    """Approval mode for agent actions."""
    AUTO = "auto"
    NOTIFY = "notify"
    REVIEW = "review"
    MANUAL = "manual"


class ExecutionStatus(str, Enum):
    """Execution status values."""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Agent Schemas
class TriggerConfig(BaseModel):
    """Trigger configuration."""
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ActionConfig(BaseModel):
    """Action configuration."""
    id: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class ApprovalConfig(BaseModel):
    """Approval configuration."""
    mode: ApprovalMode = ApprovalMode.REVIEW
    timeout_hours: int = 24
    reviewers: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    """Complete agent definition."""
    trigger: TriggerConfig
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    variables: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[ActionConfig]
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    error_handling: dict[str, Any] = Field(default_factory=dict)
    rate_limit: dict[str, Any] | None = None


class AgentCreate(BaseModel):
    """Request to create an agent."""
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    definition: AgentDefinition
    tags: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Request to update an agent."""
    display_name: str | None = None
    description: str | None = None
    definition: AgentDefinition | None = None
    status: AgentStatus | None = None
    tags: list[str] | None = None


class AgentResponse(BaseModel):
    """Agent response model."""
    id: UUID
    tenant_id: str
    name: str
    display_name: str
    description: str | None
    definition: AgentDefinition
    status: AgentStatus
    tags: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_execution_at: datetime | None
    execution_count: int
    success_count: int
    failure_count: int

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Paginated list of agents."""
    agents: list[AgentResponse]
    total: int
    limit: int
    offset: int


# Execution Schemas
class TriggerRequest(BaseModel):
    """Request to trigger an agent."""
    input_data: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class ActionResult(BaseModel):
    """Result of a single action."""
    action_id: str
    action_type: str
    status: ExecutionStatus
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int
    started_at: datetime
    completed_at: datetime | None


class ExecutionResponse(BaseModel):
    """Execution response model."""
    id: UUID
    agent_id: UUID
    tenant_id: str
    status: ExecutionStatus
    trigger_data: dict[str, Any]
    action_results: list[ActionResult]
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    error: str | None = None
    dry_run: bool = False

    class Config:
        from_attributes = True
```

### Step 9: Create Dependencies

```python
# services/agent-service/src/aswa_agents/api/dependencies.py
"""FastAPI dependencies for injection."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.config import get_settings, Settings
from aswa_agents.persistence.database import get_session


async def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


async def get_db_session() -> AsyncSession:
    """Get database session."""
    async for session in get_session():
        yield session


async def get_current_tenant(
    authorization: Annotated[str, Header()],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> str:
    """Extract tenant ID from JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Tenant ID not in token")
        return tenant_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    authorization: Annotated[str, Header()],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    """Extract user info from JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Step 10: Create Dockerfile

```dockerfile
# services/agent-service/Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .

FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Expose ports
EXPOSE 8090 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8090/health').raise_for_status()"

# Run application
CMD ["uvicorn", "aswa_agents.main:app", "--host", "0.0.0.0", "--port", "8090"]
```

## Test Cases

### Unit Tests

```python
# services/agent-service/tests/conftest.py
"""Pytest fixtures for Agent Service tests."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from aswa_agents.main import app
from aswa_agents.config import get_settings, Settings
from aswa_agents.persistence.database import Base, get_session


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return Settings(
        environment="development",
        debug=True,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_agents",
    )


@pytest.fixture
async def db_session(settings: Settings):
    """Create test database session."""
    engine = create_async_engine(str(settings.database_url), echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def test_tenant_id() -> str:
    """Get test tenant ID."""
    return f"test-tenant-{uuid4().hex[:8]}"


@pytest.fixture
def auth_headers(test_tenant_id: str, settings: Settings) -> dict:
    """Create authorization headers with valid JWT."""
    from jose import jwt

    token = jwt.encode(
        {"sub": "test-user", "tenant_id": test_tenant_id, "roles": ["admin"]},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Create test client."""
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture
async def async_client(settings: Settings) -> AsyncClient:
    """Create async test client."""
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

```python
# services/agent-service/tests/unit/test_config.py
"""Tests for configuration management."""

import pytest
from aswa_agents.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()

        assert settings.service_name == "agent-service"
        assert settings.port == 8090
        assert settings.environment == "development"
        assert not settings.is_production

    def test_production_check(self):
        """Test production environment detection."""
        settings = Settings(environment="production")
        assert settings.is_production

    def test_database_url_parsing(self):
        """Test database URL is valid."""
        settings = Settings()
        assert "postgresql" in str(settings.database_url)

    def test_get_settings_cached(self):
        """Test settings are cached."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
```

```python
# services/agent-service/tests/unit/test_api_health.py
"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "agent-service"

    def test_readiness_check(self, client: TestClient):
        """Test /ready endpoint."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
```

```python
# services/agent-service/tests/unit/test_api_schemas.py
"""Tests for API schemas."""

import pytest
from datetime import datetime
from uuid import uuid4

from aswa_agents.api.schemas import (
    AgentCreate,
    AgentDefinition,
    TriggerConfig,
    ActionConfig,
    ApprovalConfig,
    ApprovalMode,
    AgentStatus,
)


class TestAgentSchemas:
    """Test agent-related schemas."""

    def test_trigger_config_creation(self):
        """Test TriggerConfig creation."""
        trigger = TriggerConfig(
            type="email_received",
            config={"inbox": "support@example.com"},
        )

        assert trigger.type == "email_received"
        assert trigger.config["inbox"] == "support@example.com"

    def test_action_config_creation(self):
        """Test ActionConfig creation."""
        action = ActionConfig(
            id="summarize_1",
            type="summarize",
            config={"max_length": 200},
            depends_on=[],
        )

        assert action.id == "summarize_1"
        assert action.type == "summarize"

    def test_agent_definition_creation(self):
        """Test AgentDefinition creation."""
        definition = AgentDefinition(
            trigger=TriggerConfig(type="webhook"),
            actions=[
                ActionConfig(id="action_1", type="summarize"),
            ],
        )

        assert definition.trigger.type == "webhook"
        assert len(definition.actions) == 1
        assert definition.approval.mode == ApprovalMode.REVIEW

    def test_agent_create_validation(self):
        """Test AgentCreate validation."""
        agent = AgentCreate(
            name="test-agent",
            display_name="Test Agent",
            description="A test agent",
            definition=AgentDefinition(
                trigger=TriggerConfig(type="manual"),
                actions=[ActionConfig(id="a1", type="log")],
            ),
            tags=["test"],
        )

        assert agent.name == "test-agent"
        assert len(agent.tags) == 1

    def test_agent_create_name_validation(self):
        """Test name field validation."""
        with pytest.raises(ValueError):
            AgentCreate(
                name="",  # Empty name should fail
                display_name="Test",
                definition=AgentDefinition(
                    trigger=TriggerConfig(type="manual"),
                    actions=[],
                ),
            )
```

### Integration Tests

```python
# services/agent-service/tests/integration/test_agent_crud.py
"""Integration tests for agent CRUD operations."""

import pytest
from uuid import uuid4
from httpx import AsyncClient


@pytest.mark.integration
class TestAgentCRUD:
    """Test agent CRUD operations."""

    async def test_create_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test creating an agent."""
        agent_data = {
            "name": "test-agent",
            "display_name": "Test Agent",
            "description": "A test agent for integration tests",
            "definition": {
                "trigger": {"type": "manual", "config": {}},
                "actions": [
                    {"id": "action_1", "type": "log", "config": {"message": "Hello"}},
                ],
            },
            "tags": ["test", "integration"],
        }

        response = await async_client.post(
            "/api/v1/agents",
            json=agent_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-agent"
        assert data["status"] == "draft"
        assert "id" in data

    async def test_list_agents(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test listing agents."""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data

    async def test_get_agent_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting non-existent agent."""
        response = await async_client.get(
            f"/api/v1/agents/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404
```

## Verification Steps

1. **Create directory structure:**
   ```bash
   mkdir -p services/agent-service/src/aswa_agents/{api/endpoints,core,agents/builtin,actions/blocks,generation/nlp,approval,persistence,connectors,utils}
   mkdir -p services/agent-service/tests/{unit,integration}
   mkdir -p services/agent-service/alembic/versions
   touch services/agent-service/src/aswa_agents/__init__.py
   touch services/agent-service/src/aswa_agents/api/__init__.py
   touch services/agent-service/src/aswa_agents/api/endpoints/__init__.py
   ```

2. **Install dependencies:**
   ```bash
   cd services/agent-service
   pip install -e ".[dev]"
   ```

3. **Run linting:**
   ```bash
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

4. **Run unit tests:**
   ```bash
   pytest tests/unit/ -v
   ```

5. **Build Docker image:**
   ```bash
   docker build -t aswa-agent-service:dev .
   ```

6. **Run health check:**
   ```bash
   docker run -p 8090:8090 aswa-agent-service:dev &
   curl http://localhost:8090/health
   ```

## Integration Points

- **API Gateway**: Add route for `/api/v1/agents/**` → agent-service
- **Insight Service**: Subscribe to insight events for agent triggering
- **Integration Service**: Use for OAuth tokens and external system connections
- **Notification Service**: Send approval requests and execution notifications

## Next Task

Proceed to `task-9.1.2-agent-base-classes.md` to implement the core agent abstractions.
