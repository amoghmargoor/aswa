"""FastAPI application for the connector service."""

import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aswa_common.errors import AswaError
from aswa_common.logging import get_logger, setup_logging

from aswa_connector.config import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    setup_logging(service_name=settings.service_name, debug=settings.debug)
    logger.info(f"Starting {settings.service_name} v{settings.version}")

    # Initialize database
    from aswa_connector.dependencies import init_db, close_db

    await init_db()
    logger.info("Database initialized")

    # Initialize Redis
    from aswa_connector.dependencies import init_redis, close_redis

    await init_redis()
    logger.info("Redis initialized")

    # Initialize connector provider
    from aswa_connector.dependencies import init_provider

    await init_provider()
    logger.info(f"Connector provider initialized: {settings.connector.default_provider}")

    yield

    # Cleanup
    logger.info("Shutting down...")
    await close_redis()
    await close_db()


app = FastAPI(
    title="ASWA Connector Service",
    description="Data source connectors with Airbyte integration",
    version=settings.version,
    lifespan=lifespan,
)


@app.exception_handler(AswaError)
async def aswa_error_handler(request: Request, exc: AswaError) -> JSONResponse:
    """Handle ASWA errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# Register routers
from aswa_connector.api import health, connections, oauth, sync, webhooks

app.include_router(health.router, tags=["Health"])
app.include_router(oauth.router, prefix="/api/v1/oauth", tags=["OAuth"])
app.include_router(connections.router, prefix="/api/v1", tags=["Connections"])
app.include_router(sync.router, prefix="/api/v1", tags=["Sync"])
app.include_router(webhooks.router, prefix="/internal", tags=["Webhooks"])


def run() -> None:
    """Run the application."""
    uvicorn.run(
        "aswa_connector.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
