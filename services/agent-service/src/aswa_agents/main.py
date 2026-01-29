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


def run() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aswa_agents.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
    )


if __name__ == "__main__":
    run()
