from fastapi import APIRouter, Depends
import structlog

from aswa_query import __version__
from aswa_query.config import Settings, get_settings
from aswa_query.models import HealthResponse

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Health check endpoint."""
    dependencies = {}

    # Check Redis
    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url)
        await client.ping()
        dependencies["redis"] = "healthy"
        await client.close()
    except Exception as e:
        dependencies["redis"] = f"unhealthy: {str(e)}"

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url)
        client.get_collections()
        dependencies["qdrant"] = "healthy"
    except Exception as e:
        dependencies["qdrant"] = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if all("healthy" == v for v in dependencies.values()) else "degraded",
        service=settings.service_name,
        version=__version__,
        dependencies=dependencies,
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness check for Kubernetes."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Liveness check for Kubernetes."""
    return {"alive": True}
