"""ASWA Ingestion Service - Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from redis.asyncio import Redis

from aswa_common.exceptions import AswaError
from aswa_common.logging import get_logger, setup_logging

from aswa_ingestion.api import documents, health, sync
from aswa_ingestion.config import settings
from aswa_ingestion.dependencies import (
    close_db_engine,
    close_redis,
    get_db_engine,
    init_db_engine,
    init_redis,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown."""
    logger.info("Starting ASWA Ingestion Service...")

    # Initialize database engine
    logger.info("Initializing database connection...")
    await init_db_engine()

    # Initialize Redis
    logger.info("Initializing Redis connection...")
    await init_redis()

    # TODO: Initialize Qdrant client
    # TODO: Initialize background scheduler for sync jobs

    logger.info("ASWA Ingestion Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down ASWA Ingestion Service...")

    # Close Redis
    await close_redis()

    # Close database
    await close_db_engine()

    logger.info("ASWA Ingestion Service shut down gracefully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging(settings.ingestion.log_level)

    app = FastAPI(
        title="ASWA Ingestion Service",
        description="Document ingestion and processing pipeline for ASWA",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure from settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(sync.router, prefix="/api/v1", tags=["Sync"])
    app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])

    # Mount Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # Exception handlers
    @app.exception_handler(AswaError)
    async def aswa_exception_handler(request: Request, exc: AswaError) -> JSONResponse:
        """Handle ASWA exceptions."""
        logger.error(f"AswaError: {exc.error_code} - {exc.message}", exc_info=exc)
        return JSONResponse(
            status_code=_map_error_code_to_status(exc.error_code),
            content={
                "error_code": exc.error_code.value,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(f"Unexpected error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(exc)} if settings.ingestion.debug else {},
            },
        )

    return app


def _map_error_code_to_status(error_code) -> int:
    """Map error codes to HTTP status codes."""
    from aswa_common.exceptions import ErrorCode

    mapping = {
        ErrorCode.VALIDATION_ERROR: 400,
        ErrorCode.INVALID_INPUT: 400,
        ErrorCode.AUTHENTICATION_FAILED: 401,
        ErrorCode.INVALID_CREDENTIALS: 401,
        ErrorCode.AUTHORIZATION_FAILED: 403,
        ErrorCode.INSUFFICIENT_PERMISSIONS: 403,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.RESOURCE_CONFLICT: 409,
        ErrorCode.DUPLICATE_RESOURCE: 409,
        ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    }
    return mapping.get(error_code, 500)


app = create_app()


def run() -> None:
    """Run the application with uvicorn."""
    uvicorn.run(
        "aswa_ingestion.main:app",
        host="0.0.0.0",
        port=settings.ingestion.service_port,
        reload=settings.ingestion.debug,
        log_level=settings.ingestion.log_level.lower(),
    )


if __name__ == "__main__":
    run()
