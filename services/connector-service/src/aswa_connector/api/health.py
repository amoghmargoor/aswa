"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from aswa_connector.config import settings
from aswa_connector.dependencies import DbSession, RedisClient

router = APIRouter()


@router.get("/health")
async def liveness() -> dict[str, Any]:
    """Liveness check - service is running."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness(
    db: DbSession,
    redis: RedisClient,
) -> dict[str, Any]:
    """Readiness check - service is ready to handle requests."""
    checks: dict[str, Any] = {}

    # Check database
    try:
        from sqlalchemy import text

        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # Check Airbyte
    try:
        from aswa_connector.providers.airbyte.client import AirbyteClient

        client = AirbyteClient()
        airbyte_healthy = await client.health_check()
        await client.close()
        checks["airbyte"] = {
            "status": "healthy" if airbyte_healthy else "unhealthy"
        }
    except Exception as e:
        checks["airbyte"] = {"status": "unhealthy", "error": str(e)}

    # Overall status
    all_healthy = all(c.get("status") == "healthy" for c in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
