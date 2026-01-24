"""Dependency injection for the connector service."""

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aswa_common.logging import get_logger

from aswa_connector.config import settings

logger = get_logger(__name__)

# Global instances
_engine: Any = None
_session_factory: Any = None
_redis: Redis | None = None
_provider: Any = None


async def init_db() -> None:
    """Initialize database connection."""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database.url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.pool_overflow,
        echo=settings.debug,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def close_db() -> None:
    """Close database connection."""
    global _engine
    if _engine:
        await _engine.dispose()


async def init_redis() -> None:
    """Initialize Redis connection."""
    global _redis
    _redis = Redis.from_url(settings.redis.url)
    await _redis.ping()


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis
    if _redis:
        await _redis.close()


async def init_provider() -> None:
    """Initialize connector provider."""
    global _provider

    from aswa_connector.framework.registry import get_provider

    _provider = await get_provider(settings.connector.default_provider)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Get Redis client."""
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    yield _redis


async def get_provider() -> Any:
    """Get connector provider."""
    if _provider is None:
        raise RuntimeError("Provider not initialized")
    return _provider


async def get_tenant_context(
    x_tenant_id: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_roles: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Extract tenant context from headers."""
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="X-Tenant-Id header required")

    from uuid import UUID

    try:
        tenant_id = UUID(x_tenant_id)
        user_id = UUID(x_user_id) if x_user_id else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    roles = x_user_roles.split(",") if x_user_roles else []

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "roles": roles,
    }


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[Redis, Depends(get_redis)]
TenantCtx = Annotated[dict[str, Any], Depends(get_tenant_context)]
Provider = Annotated[Any, Depends(get_provider)]
