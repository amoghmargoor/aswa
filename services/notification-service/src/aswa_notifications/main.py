from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog
import uvicorn

from aswa_notifications.config import get_settings
from aswa_notifications.api.routes import (
    router,
    set_notification_service,
    set_preference_service,
)
from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.services.preference_service import PreferenceService

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info("Starting notification service", environment=settings.environment)

    # Initialize notification service
    notification_service = NotificationService()
    await notification_service.initialize()
    set_notification_service(notification_service)

    # Initialize preference service
    preference_service = PreferenceService(notification_service._session_factory)
    set_preference_service(preference_service)

    logger.info("Notification service ready")

    yield

    # Cleanup
    await notification_service.close()
    logger.info("Notification service stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Notification Service",
        description="Notification service for ASWA platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": settings.service_name}

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "aswa_notifications.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
