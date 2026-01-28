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
