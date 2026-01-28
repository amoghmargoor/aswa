"""Background worker that processes jobs from a Redis queue.

Supports graceful shutdown and concurrent processing with metrics.
"""

import asyncio
import signal
from typing import Any, Awaitable, Callable

import structlog
from prometheus_client import Counter, Gauge, Histogram

from aswa_processor.queue import QueueMessage, RedisQueue

logger = structlog.get_logger()


# Prometheus metrics
JOBS_PROCESSED = Counter(
    "worker_jobs_processed_total",
    "Total jobs processed",
    ["status"],
)

JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Job processing duration",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

ACTIVE_JOBS = Gauge(
    "worker_active_jobs",
    "Currently processing jobs",
)

QUEUE_LENGTH = Gauge(
    "worker_queue_length",
    "Current queue length",
)

QUEUE_PENDING = Gauge(
    "worker_queue_pending",
    "Pending messages in consumer group",
)


class Worker:
    """Background worker that processes jobs from a Redis queue.

    Supports graceful shutdown and concurrent processing with:
    - Configurable concurrency via semaphore
    - Job timeouts
    - Automatic retries
    - Prometheus metrics
    - Signal handling for graceful shutdown
    """

    def __init__(
        self,
        queue: RedisQueue,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        concurrency: int = 4,
        batch_size: int = 10,
        poll_interval: float = 5.0,
        max_retries: int = 3,
        job_timeout: float = 300.0,
    ) -> None:
        """Initialize worker.

        Args:
            queue: Redis queue to process from
            handler: Async function to handle job payloads
            concurrency: Maximum concurrent jobs
            batch_size: Jobs to fetch per poll
            poll_interval: Seconds between queue polls
            max_retries: Maximum retry attempts per job
            job_timeout: Job timeout in seconds
        """
        self.queue = queue
        self.handler = handler
        self.concurrency = concurrency
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.job_timeout = job_timeout

        self._running = False
        self._tasks: set[asyncio.Task[None]] = set()
        self._semaphore = asyncio.Semaphore(concurrency)
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the worker."""
        logger.info(
            "Starting worker",
            concurrency=self.concurrency,
            batch_size=self.batch_size,
            poll_interval=self.poll_interval,
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler)

        # Initialize queue
        await self.queue.initialize()

        self._running = True
        self._shutdown_event.clear()

        # Start metrics updater
        metrics_task = asyncio.create_task(self._update_metrics())

        # Main processing loop
        try:
            await self._processing_loop()
        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass
            await self._shutdown()

    async def _processing_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                messages = await self.queue.dequeue(
                    count=self.batch_size,
                    block_ms=int(self.poll_interval * 1000),
                )

                for message in messages:
                    if not self._running:
                        break

                    task = asyncio.create_task(self._process_message(message))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)

                # Yield to allow other tasks to run
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in processing loop", error=str(e), exc_info=True)
                await asyncio.sleep(1)  # Brief pause on error

    async def _process_message(self, message: QueueMessage) -> None:
        """Process a single message with concurrency control.

        Args:
            message: Queue message to process
        """
        async with self._semaphore:
            ACTIVE_JOBS.inc()
            start_time = asyncio.get_event_loop().time()

            try:
                logger.info(
                    "Processing job",
                    msg_id=message.id,
                    attempt=message.attempts + 1,
                )

                # Add timeout
                async with asyncio.timeout(self.job_timeout):
                    await self.handler(message.payload)

                await self.queue.ack(message.id)
                JOBS_PROCESSED.labels(status="success").inc()

                duration = asyncio.get_event_loop().time() - start_time
                JOB_DURATION.observe(duration)
                logger.info(
                    "Job completed",
                    msg_id=message.id,
                    duration=f"{duration:.2f}s",
                )

            except asyncio.TimeoutError:
                logger.error("Job timed out", msg_id=message.id)
                await self.queue.nack(message.id, retry=True, max_retries=self.max_retries)
                JOBS_PROCESSED.labels(status="timeout").inc()

            except Exception as e:
                logger.error(
                    "Job failed",
                    msg_id=message.id,
                    error=str(e),
                    exc_info=True,
                )
                await self.queue.nack(message.id, retry=True, max_retries=self.max_retries)
                JOBS_PROCESSED.labels(status="error").inc()

            finally:
                ACTIVE_JOBS.dec()

    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._running = False
        self._shutdown_event.set()

    async def stop(self) -> None:
        """Request worker stop."""
        self._running = False
        self._shutdown_event.set()

    async def _shutdown(self) -> None:
        """Graceful shutdown - wait for active jobs to complete."""
        logger.info("Shutting down worker", active_tasks=len(self._tasks))

        if self._tasks:
            # Wait for active tasks with timeout
            done, pending = await asyncio.wait(
                self._tasks,
                timeout=60,  # 60 second grace period
            )

            if pending:
                logger.warning("Cancelling pending tasks", count=len(pending))
                for task in pending:
                    task.cancel()

                # Wait for cancellation
                await asyncio.gather(*pending, return_exceptions=True)

        logger.info("Worker shutdown complete")

    async def _update_metrics(self) -> None:
        """Periodically update queue metrics."""
        while self._running:
            try:
                stats = await self.queue.get_queue_stats()
                QUEUE_LENGTH.set(stats["length"])
                QUEUE_PENDING.set(stats["pending"])
            except Exception as e:
                logger.warning("Failed to update metrics", error=str(e))

            await asyncio.sleep(30)

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    @property
    def active_jobs(self) -> int:
        """Get number of active jobs."""
        return len(self._tasks)
