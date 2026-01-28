"""Main entry point for the document processor worker."""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as redis
import structlog
from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aswa_processor.config import database_settings, redis_settings, settings
from aswa_processor.handlers import DocumentProcessingHandler
from aswa_processor.queue import RedisQueue
from aswa_processor.worker import Worker

logger = structlog.get_logger()


def configure_logging(json_output: bool = True) -> None:
    """Configure structured logging.

    Args:
        json_output: Use JSON format for production
    """
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


class AsyncSessionFactory:
    """Factory for creating async database sessions."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """Initialize factory.

        Args:
            session_maker: SQLAlchemy async session maker
        """
        self._session_maker = session_maker

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[AsyncSession, None]:
        """Create a new session context."""
        async with self._session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class MockPipeline:
    """Mock pipeline for testing without full ingestion service."""

    async def process(self, document: Any) -> Any:
        """Mock process method."""
        import time
        from dataclasses import dataclass

        @dataclass
        class Result:
            chunks_created: int = 10
            vectors_stored: int = 10
            processing_time_ms: int = 100

        # Simulate processing
        await asyncio.sleep(0.1)
        return Result()


async def create_dependencies() -> tuple[RedisQueue, DocumentProcessingHandler]:
    """Create worker dependencies.

    Returns:
        Tuple of (queue, handler)
    """
    # Create database engine
    engine = create_async_engine(
        database_settings.async_url,
        pool_size=database_settings.pool_size,
        echo=False,
    )

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session_factory = AsyncSessionFactory(session_maker)

    # Create Redis client
    redis_client = redis.from_url(
        redis_settings.url,
        max_connections=redis_settings.max_connections,
    )

    # Create queue
    queue = RedisQueue(
        redis_client=redis_client,
        queue_name=settings.queue_name,
        consumer_group="document-processors",
        consumer_name=f"processor-{os.getpid()}",
        dlq_name=settings.dead_letter_queue,
    )

    # Create pipeline
    try:
        from aswa_ingestion.processing.pipeline import DocumentProcessingPipeline

        # Initialize with required components
        pipeline = DocumentProcessingPipeline()
    except ImportError:
        logger.warning("Using mock pipeline - ingestion service not available")
        pipeline = MockPipeline()

    # Create handler
    handler = DocumentProcessingHandler(
        session_factory=session_factory,
        pipeline=pipeline,
    )

    return queue, handler


async def main() -> None:
    """Main entry point."""
    # Configure logging
    json_output = os.getenv("LOG_FORMAT", "json") == "json"
    configure_logging(json_output=json_output)

    logger.info(
        "Starting document processor",
        worker_name=settings.worker_name,
        concurrency=settings.concurrency,
        queue=settings.queue_name,
    )

    # Start Prometheus metrics server
    metrics_port = int(os.getenv("METRICS_PORT", "9090"))
    start_http_server(metrics_port)
    logger.info("Metrics server started", port=metrics_port)

    # Create dependencies
    queue, handler = await create_dependencies()

    # Create and start worker
    worker = Worker(
        queue=queue,
        handler=handler,
        concurrency=settings.concurrency,
        batch_size=settings.batch_size,
        poll_interval=settings.poll_interval_seconds,
        max_retries=settings.max_retries,
        job_timeout=settings.processing_timeout_seconds,
    )

    await worker.start()


def run() -> None:
    """Entry point for poetry script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
