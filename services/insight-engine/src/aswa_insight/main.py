"""FastAPI application for the Insight Engine service."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aswa_insight.config import settings

logger = structlog.get_logger()


def configure_logging(json_output: bool = True) -> None:
    """Configure structured logging."""
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    configure_logging(json_output=not settings.insight.debug)
    logger.info(
        "Starting Insight Engine service",
        service=settings.insight.service_name,
        llm_provider=settings.insight.llm_provider,
    )

    # Initialize LLM client
    from aswa_insight.llm import get_llm_client

    app.state.llm_client = await get_llm_client()
    logger.info("LLM client initialized", provider=settings.insight.llm_provider)

    # Initialize database
    engine = create_async_engine(
        settings.database.async_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        echo=settings.insight.debug,
    )

    app.state.session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.db_engine = engine
    logger.info("Database connection established")

    yield

    # Shutdown
    logger.info("Shutting down Insight Engine service")
    await engine.dispose()


app = FastAPI(
    title="ASWA Insight Engine",
    description="LLM-powered insight extraction service",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
from aswa_insight.api import extraction, health, insights

app.include_router(health.router, tags=["health"])
app.include_router(extraction.router, prefix="/api/v1", tags=["extraction"])
app.include_router(insights.router, prefix="/api/v1", tags=["insights"])


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={"error": "validation_error", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.error("Unhandled exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )


def run() -> None:
    """Entry point for running the service."""
    uvicorn.run(
        "aswa_insight.main:app",
        host="0.0.0.0",
        port=settings.insight.service_port,
        reload=settings.insight.debug,
    )


if __name__ == "__main__":
    run()
