"""API endpoints for the Insight Engine service."""

from aswa_insight.api.health import router as health_router
from aswa_insight.api.extraction import router as extraction_router
from aswa_insight.api.insights import router as insights_router

__all__ = ["health_router", "extraction_router", "insights_router"]
