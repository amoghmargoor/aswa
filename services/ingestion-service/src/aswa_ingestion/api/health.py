"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from redis.asyncio import Redis

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings
from aswa_ingestion.dependencies import DbSession, get_db_engine, get_redis

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Basic health check endpoint.

    Returns:
        Basic health status
    """
    return {
        "status": "UP",
        "service": settings.ingestion.service_name,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def ready(db: DbSession) -> dict[str, Any]:
    """Readiness check with dependency verification.

    Checks:
        - Database connectivity
        - Redis connectivity

    Returns:
        Readiness status with component health
    """
    logger.debug("Readiness check requested")

    checks: dict[str, dict[str, Any]] = {}

    # Check database
    try:
        from sqlalchemy import text

        result = await db.execute(text("SELECT 1"))
        result.scalar()
        checks["database"] = {"status": "UP"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "DOWN", "error": str(e)}

    # Check Redis
    try:
        redis: Redis = await get_redis()
        await redis.ping()
        checks["redis"] = {"status": "UP"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = {"status": "DOWN", "error": str(e)}

    # Overall status
    all_up = all(check.get("status") == "UP" for check in checks.values())
    status = "READY" if all_up else "NOT_READY"

    return {
        "status": status,
        "service": settings.ingestion.service_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
