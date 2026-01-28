"""Health check endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Request

from aswa_insight.config import settings

logger = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe endpoint."""
    return {
        "status": "healthy",
        "service": settings.insight.service_name,
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, Any]:
    """Readiness probe endpoint."""
    checks: dict[str, dict[str, Any]] = {}

    # Check LLM client
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client:
        try:
            is_healthy = await llm_client.health_check()
            checks["llm"] = {"status": "healthy" if is_healthy else "unhealthy"}
        except Exception as e:
            checks["llm"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["llm"] = {"status": "not_initialized"}

    # Check database
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            async with session_factory() as session:
                await session.execute("SELECT 1")
            checks["database"] = {"status": "healthy"}
        except Exception as e:
            checks["database"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["database"] = {"status": "not_initialized"}

    # Determine overall status
    all_healthy = all(
        check.get("status") == "healthy" for check in checks.values()
    )

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/health/live")
async def live() -> dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}
