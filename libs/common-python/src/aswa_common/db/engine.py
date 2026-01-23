"""Database engine factory for async SQLAlchemy."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(
    database_url: str,
    pool_size: int = 5,
    max_overflow: int = 10,
    echo: bool = False,
) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling.

    Args:
        database_url: PostgreSQL connection URL (must use postgresql+asyncpg://)
        pool_size: Number of connections to maintain in the pool
        max_overflow: Maximum overflow connections beyond pool_size
        echo: If True, log all SQL statements

    Returns:
        Configured async engine

    Example:
        >>> from aswa_common.config import DatabaseSettings
        >>> settings = DatabaseSettings()
        >>> engine = create_engine(settings.async_url)
    """
    return create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        # Verify connections before use to avoid stale connections
        pool_pre_ping=True,
        # Recycle connections after 1 hour to prevent long-lived connection issues
        pool_recycle=3600,
        # Use pessimistic connection testing for better reliability
        pool_use_lifo=True,
    )
