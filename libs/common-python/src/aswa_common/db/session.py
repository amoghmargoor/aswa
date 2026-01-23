"""Database session management for async SQLAlchemy."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aswa_common.logging import get_logger

logger = get_logger(__name__)


class AsyncSessionFactory:
    """Factory for creating async database sessions."""

    def __init__(self, engine: AsyncEngine) -> None:
        """Initialize session factory with engine.

        Args:
            engine: Async SQLAlchemy engine
        """
        self.engine = engine
        self._session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    def create_session(self) -> AsyncSession:
        """Create a new async session.

        Returns:
            New async session instance

        Note:
            Caller is responsible for closing the session.
            Prefer using the session() context manager instead.
        """
        return self._session_factory()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for session with automatic commit/rollback.

        Yields:
            Async database session

        Example:
            >>> async with factory.session() as session:
            ...     user = await session.get(User, user_id)
            ...     user.name = "New Name"
            ...     # Automatically commits on successful exit
        """
        session = self.create_session()
        try:
            yield session
            await session.commit()
            logger.debug("Database session committed successfully")
        except Exception as e:
            await session.rollback()
            logger.error("Database session rolled back", exc_info=e)
            raise
        finally:
            await session.close()


# Global session factory instance (to be initialized by application)
_session_factory: AsyncSessionFactory | None = None


def initialize_session_factory(engine: AsyncEngine) -> None:
    """Initialize the global session factory.

    Args:
        engine: Async SQLAlchemy engine

    Note:
        This should be called once during application startup.
    """
    global _session_factory
    _session_factory = AsyncSessionFactory(engine)
    logger.info("Database session factory initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        Async database session

    Raises:
        RuntimeError: If session factory not initialized

    Example:
        >>> from fastapi import Depends
        >>> @app.get("/users/{user_id}")
        >>> async def get_user(
        ...     user_id: UUID,
        ...     session: AsyncSession = Depends(get_db)
        ... ):
        ...     user = await session.get(User, user_id)
        ...     return user
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call initialize_session_factory() first."
        )

    async with _session_factory.session() as session:
        yield session
