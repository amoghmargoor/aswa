from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.api.routes import router as integration_router
from aswa_integrations.api.webhook_routes import router as webhook_router, set_webhook_manager
from aswa_integrations.api.dependencies import set_integration_manager
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.services.webhook_manager import WebhookManager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Initialize integration manager
    integration_manager = IntegrationManager()
    await integration_manager.initialize()
    set_integration_manager(integration_manager)

    # Initialize webhook manager
    webhook_manager = WebhookManager()
    await webhook_manager.initialize()
    set_webhook_manager(webhook_manager)

    logger.info(
        "Integration service started",
        environment=settings.environment,
    )

    yield

    # Cleanup
    await integration_manager.close()
    await webhook_manager.close()
    logger.info("Integration service stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Integration Service",
        description="Manages external integrations and webhooks for ASWA",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(integration_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.service_name}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aswa_integrations.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
