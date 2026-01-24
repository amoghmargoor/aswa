"""API routers for the ingestion service."""

from aswa_ingestion.api.documents import router as documents_router
from aswa_ingestion.api.health import router as health_router
from aswa_ingestion.api.sync import router as sync_router

__all__ = ["health_router", "sync_router", "documents_router"]
