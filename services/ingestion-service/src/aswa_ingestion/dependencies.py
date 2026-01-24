"""Dependency injection for the ingestion service."""

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings

logger = get_logger(__name__)

# Global instances
_db_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: Redis | None = None


# Database
async def init_db_engine() -> None:
    """Initialize database engine."""
    global _db_engine, _session_factory

    logger.info(f"Connecting to database at {settings.database.host}:{settings.database.port}")

    _db_engine = create_async_engine(
        settings.database.url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.ingestion.debug,
    )

    _session_factory = async_sessionmaker(
        bind=_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    logger.info("Database engine initialized")


async def close_db_engine() -> None:
    """Close database engine."""
    global _db_engine, _session_factory

    if _db_engine:
        await _db_engine.dispose()
        _db_engine = None
        _session_factory = None
        logger.info("Database engine closed")


def get_db_engine() -> AsyncEngine:
    """Get database engine."""
    if _db_engine is None:
        raise RuntimeError("Database engine not initialized")
    return _db_engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized")

    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Redis
async def init_redis() -> None:
    """Initialize Redis client."""
    global _redis_client

    logger.info(f"Connecting to Redis at {settings.redis.host}:{settings.redis.port}")

    _redis_client = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password or None,
        db=settings.redis.db,
        decode_responses=True,
        max_connections=settings.redis.max_connections,
    )

    # Test connection
    await _redis_client.ping()
    logger.info("Redis connection established")


async def close_redis() -> None:
    """Close Redis client."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


async def get_redis() -> Redis:
    """Get Redis client dependency."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client


# Tenant Context
class TenantContext:
    """Tenant context extracted from request headers."""

    def __init__(self, tenant_id: UUID, user_id: UUID, roles: list[str]):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.roles = roles

    def has_role(self, role: str) -> bool:
        """Check if user has role."""
        return role in self.roles


async def get_tenant_context(
    x_tenant_id: Annotated[str, Header()],
    x_user_id: Annotated[str, Header()],
    x_user_roles: Annotated[str, Header()] = "",
) -> TenantContext:
    """Extract tenant context from headers.

    In production, these headers are set by the API Gateway after JWT validation.
    """
    try:
        tenant_id = UUID(x_tenant_id)
        user_id = UUID(x_user_id)
        roles = [r.strip() for r in x_user_roles.split(",") if r.strip()]
        return TenantContext(tenant_id, user_id, roles)
    except ValueError as e:
        logger.warning(f"Invalid tenant context headers: {e}")
        raise HTTPException(status_code=400, detail="Invalid tenant context headers")


# Type aliases for FastAPI dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
TenantCtx = Annotated[TenantContext, Depends(get_tenant_context)]
