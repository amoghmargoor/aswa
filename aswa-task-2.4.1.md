# Task 2.4.1: Background Worker Infrastructure

## Subtask: Create Document Processor Worker

**Claude Code Prompt:**
```
Create the document processor worker at /workers/document-processor/.

1. /workers/document-processor/pyproject.toml:
[tool.poetry]
name = "aswa-document-processor"
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11,<3.13"
aswa-common = { path = "../../libs/common-python", develop = true }
aswa-ingestion = { path = "../../services/ingestion-service", develop = true }
redis = ">=5.0"
prefect = ">=2.14"
structlog = ">=24.1"

[tool.poetry.group.dev.dependencies]
pytest = ">=8.0"
pytest-asyncio = ">=0.23"
fakeredis = ">=2.21"

2. /workers/document-processor/src/aswa_processor/__init__.py

3. /workers/document-processor/src/aswa_processor/config.py:
from pydantic_settings import BaseSettings, SettingsConfigDict

class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WORKER_")
    
    # Worker config
    worker_name: str = "document-processor"
    concurrency: int = 4
    batch_size: int = 10
    poll_interval_seconds: int = 5
    max_retries: int = 3
    retry_delay_seconds: int = 60
    
    # Queue config
    queue_name: str = "document_processing"
    dead_letter_queue: str = "document_processing_dlq"
    visibility_timeout_seconds: int = 300
    
    # Processing limits
    max_document_size_mb: int = 50
    processing_timeout_seconds: int = 300

settings = WorkerSettings()

4. /workers/document-processor/src/aswa_processor/queue.py:
import redis.asyncio as redis
import json
from datetime import datetime, timedelta
from typing import AsyncIterator
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class QueueMessage:
    id: str
    payload: dict
    attempts: int
    created_at: datetime
    
class RedisQueue:
    """
    Redis-based job queue with visibility timeout and dead letter queue.
    Uses Redis Streams for reliable message delivery.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        queue_name: str,
        consumer_group: str,
        consumer_name: str,
        dlq_name: str | None = None
    ):
        self.redis = redis_client
        self.queue_name = queue_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.dlq_name = dlq_name or f"{queue_name}_dlq"
    
    async def initialize(self) -> None:
        """Create consumer group if not exists."""
        try:
            await self.redis.xgroup_create(
                self.queue_name, 
                self.consumer_group, 
                id="0",
                mkstream=True
            )
            logger.info("Consumer group created", group=self.consumer_group)
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer group already exists")
            else:
                raise
    
    async def enqueue(
        self, 
        payload: dict,
        priority: int = 0,
        delay_seconds: int = 0
    ) -> str:
        """Add job to queue. Returns message ID."""
        message = {
            "payload": json.dumps(payload),
            "priority": priority,
            "attempts": 0,
            "created_at": datetime.utcnow().isoformat(),
            "process_after": (
                datetime.utcnow() + timedelta(seconds=delay_seconds)
            ).isoformat() if delay_seconds else ""
        }
        
        msg_id = await self.redis.xadd(self.queue_name, message)
        logger.debug("Job enqueued", queue=self.queue_name, msg_id=msg_id)
        return msg_id
    
    async def enqueue_batch(self, payloads: list[dict]) -> list[str]:
        """Add multiple jobs to queue."""
        pipe = self.redis.pipeline()
        for payload in payloads:
            message = {
                "payload": json.dumps(payload),
                "priority": 0,
                "attempts": 0,
                "created_at": datetime.utcnow().isoformat()
            }
            pipe.xadd(self.queue_name, message)
        
        results = await pipe.execute()
        return results
    
    async def dequeue(
        self,
        count: int = 1,
        block_ms: int = 5000
    ) -> list[QueueMessage]:
        """
        Fetch pending jobs from queue.
        Uses XREADGROUP for consumer group semantics.
        """
        # First, claim any pending messages that timed out
        await self._claim_stale_messages()
        
        # Read new messages
        messages = await self.redis.xreadgroup(
            groupname=self.consumer_group,
            consumername=self.consumer_name,
            streams={self.queue_name: ">"},
            count=count,
            block=block_ms
        )
        
        result = []
        if messages:
            for stream_name, stream_messages in messages:
                for msg_id, fields in stream_messages:
                    # Check delay
                    process_after = fields.get(b"process_after", b"").decode()
                    if process_after and datetime.fromisoformat(process_after) > datetime.utcnow():
                        continue
                    
                    result.append(QueueMessage(
                        id=msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                        payload=json.loads(fields[b"payload"]),
                        attempts=int(fields.get(b"attempts", 0)),
                        created_at=datetime.fromisoformat(fields[b"created_at"].decode())
                    ))
        
        return result
    
    async def _claim_stale_messages(self, min_idle_ms: int = 300000) -> None:
        """Claim messages that have been pending too long."""
        try:
            pending = await self.redis.xpending_range(
                self.queue_name,
                self.consumer_group,
                min="-",
                max="+",
                count=100
            )
            
            stale_ids = [
                p["message_id"] 
                for p in pending 
                if p["time_since_delivered"] > min_idle_ms
            ]
            
            if stale_ids:
                await self.redis.xclaim(
                    self.queue_name,
                    self.consumer_group,
                    self.consumer_name,
                    min_idle_time=min_idle_ms,
                    message_ids=stale_ids
                )
                logger.info("Claimed stale messages", count=len(stale_ids))
                
        except Exception as e:
            logger.warning("Failed to claim stale messages", error=str(e))
    
    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing."""
        await self.redis.xack(self.queue_name, self.consumer_group, message_id)
        await self.redis.xdel(self.queue_name, message_id)
        logger.debug("Message acknowledged", msg_id=message_id)
    
    async def nack(
        self, 
        message_id: str, 
        retry: bool = True,
        max_retries: int = 3
    ) -> None:
        """Negative acknowledge - return to queue or send to DLQ."""
        # Get current attempt count
        messages = await self.redis.xrange(self.queue_name, message_id, message_id)
        if not messages:
            return
        
        _, fields = messages[0]
        attempts = int(fields.get(b"attempts", 0)) + 1
        
        if retry and attempts < max_retries:
            # Update attempt count and release back to queue
            await self.redis.xadd(
                self.queue_name,
                {
                    "payload": fields[b"payload"],
                    "attempts": attempts,
                    "created_at": fields[b"created_at"],
                    "process_after": (
                        datetime.utcnow() + timedelta(seconds=60 * attempts)
                    ).isoformat()  # Exponential backoff
                }
            )
            logger.info("Message requeued", msg_id=message_id, attempt=attempts)
        else:
            # Send to dead letter queue
            await self.redis.xadd(
                self.dlq_name,
                {
                    "original_id": message_id,
                    "payload": fields[b"payload"],
                    "attempts": attempts,
                    "failed_at": datetime.utcnow().isoformat(),
                    "created_at": fields[b"created_at"]
                }
            )
            logger.warning("Message sent to DLQ", msg_id=message_id, attempts=attempts)
        
        # Remove from main queue
        await self.redis.xack(self.queue_name, self.consumer_group, message_id)
        await self.redis.xdel(self.queue_name, message_id)
    
    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        info = await self.redis.xinfo_stream(self.queue_name)
        groups = await self.redis.xinfo_groups(self.queue_name)
        
        pending_count = 0
        for group in groups:
            if group["name"].decode() == self.consumer_group:
                pending_count = group["pending"]
        
        return {
            "length": info["length"],
            "pending": pending_count,
            "first_entry": info.get("first-entry"),
            "last_entry": info.get("last-entry")
        }

5. /workers/document-processor/src/aswa_processor/worker.py:
import asyncio
import signal
from typing import Callable, Awaitable
import structlog
from prometheus_client import Counter, Histogram, Gauge

logger = structlog.get_logger()

class Worker:
    """
    Background worker that processes jobs from a Redis queue.
    Supports graceful shutdown and concurrent processing.
    """
    
    def __init__(
        self,
        queue: RedisQueue,
        handler: Callable[[dict], Awaitable[None]],
        concurrency: int = 4,
        batch_size: int = 10,
        poll_interval: float = 5.0,
        max_retries: int = 3
    ):
        self.queue = queue
        self.handler = handler
        self.concurrency = concurrency
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(concurrency)
        
        # Metrics
        self._jobs_processed = Counter(
            "worker_jobs_processed_total",
            "Total jobs processed",
            ["status"]
        )
        self._job_duration = Histogram(
            "worker_job_duration_seconds",
            "Job processing duration"
        )
        self._active_jobs = Gauge(
            "worker_active_jobs",
            "Currently processing jobs"
        )
        self._queue_length = Gauge(
            "worker_queue_length",
            "Current queue length"
        )
    
    async def start(self) -> None:
        """Start the worker."""
        logger.info("Starting worker", concurrency=self.concurrency)
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler)
        
        # Initialize queue
        await self.queue.initialize()
        
        self._running = True
        
        # Start metrics updater
        metrics_task = asyncio.create_task(self._update_metrics())
        
        # Main processing loop
        try:
            while self._running:
                messages = await self.queue.dequeue(
                    count=self.batch_size,
                    block_ms=int(self.poll_interval * 1000)
                )
                
                for message in messages:
                    task = asyncio.create_task(self._process_message(message))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                
                # Yield to allow other tasks to run
                await asyncio.sleep(0)
                
        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            metrics_task.cancel()
            await self._shutdown()
    
    async def _process_message(self, message: QueueMessage) -> None:
        """Process a single message with concurrency control."""
        async with self._semaphore:
            self._active_jobs.inc()
            start_time = asyncio.get_event_loop().time()
            
            try:
                logger.info("Processing job", msg_id=message.id, attempt=message.attempts + 1)
                
                # Add timeout
                async with asyncio.timeout(300):  # 5 minute timeout
                    await self.handler(message.payload)
                
                await self.queue.ack(message.id)
                self._jobs_processed.labels(status="success").inc()
                
                duration = asyncio.get_event_loop().time() - start_time
                self._job_duration.observe(duration)
                logger.info("Job completed", msg_id=message.id, duration=f"{duration:.2f}s")
                
            except asyncio.TimeoutError:
                logger.error("Job timed out", msg_id=message.id)
                await self.queue.nack(message.id, retry=True, max_retries=self.max_retries)
                self._jobs_processed.labels(status="timeout").inc()
                
            except Exception as e:
                logger.error("Job failed", msg_id=message.id, error=str(e), exc_info=True)
                await self.queue.nack(message.id, retry=True, max_retries=self.max_retries)
                self._jobs_processed.labels(status="error").inc()
                
            finally:
                self._active_jobs.dec()
    
    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._running = False
    
    async def _shutdown(self) -> None:
        """Graceful shutdown - wait for active jobs to complete."""
        logger.info("Shutting down worker", active_tasks=len(self._tasks))
        
        if self._tasks:
            # Wait for active tasks with timeout
            done, pending = await asyncio.wait(
                self._tasks,
                timeout=60  # 60 second grace period
            )
            
            if pending:
                logger.warning("Cancelling pending tasks", count=len(pending))
                for task in pending:
                    task.cancel()
        
        logger.info("Worker shutdown complete")
    
    async def _update_metrics(self) -> None:
        """Periodically update queue metrics."""
        while self._running:
            try:
                stats = await self.queue.get_queue_stats()
                self._queue_length.set(stats["length"])
            except Exception as e:
                logger.warning("Failed to update metrics", error=str(e))
            
            await asyncio.sleep(30)

6. /workers/document-processor/src/aswa_processor/handlers.py:
from aswa_ingestion.processing.pipeline import DocumentProcessingPipeline
from aswa_common.db import AsyncSessionFactory
from uuid import UUID
import structlog

logger = structlog.get_logger()

class DocumentProcessingHandler:
    """Handler for document processing jobs."""
    
    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        pipeline: DocumentProcessingPipeline
    ):
        self.session_factory = session_factory
        self.pipeline = pipeline
    
    async def __call__(self, payload: dict) -> None:
        """
        Process a document.
        
        Payload format:
        {
            "document_id": "uuid",
            "tenant_id": "uuid",
            "reprocess": false
        }
        """
        document_id = UUID(payload["document_id"])
        tenant_id = UUID(payload["tenant_id"])
        reprocess = payload.get("reprocess", False)
        
        async with self.session_factory.session() as session:
            # Fetch document
            from aswa_common.db.repositories import DocumentRepository
            repo = DocumentRepository(session, tenant_id)
            document = await repo.get_by_id(document_id)
            
            if not document:
                logger.warning("Document not found", document_id=str(document_id))
                return
            
            if document.processed_status == "completed" and not reprocess:
                logger.info("Document already processed", document_id=str(document_id))
                return
            
            # Update status to processing
            await repo.update_status(document_id, "processing")
            
            try:
                # Run processing pipeline
                result = await self.pipeline.process(document)
                
                logger.info(
                    "Document processed",
                    document_id=str(document_id),
                    chunks=result.chunks_created,
                    vectors=result.vectors_stored,
                    duration_ms=result.processing_time_ms
                )
                
            except Exception as e:
                await repo.update_status(document_id, "failed", str(e))
                raise

7. /workers/document-processor/src/aswa_processor/main.py:
import asyncio
from aswa_common.logging import configure_logging
from aswa_common.config import DatabaseSettings, RedisSettings
from aswa_common.db import create_engine, AsyncSessionFactory
from .config import settings
from .queue import RedisQueue
from .worker import Worker
from .handlers import DocumentProcessingHandler

async def main():
    configure_logging(settings.worker_name, json_output=True)
    
    # Initialize dependencies
    db_settings = DatabaseSettings()
    redis_settings = RedisSettings()
    
    engine = create_engine(db_settings.async_url)
    session_factory = AsyncSessionFactory(engine)
    
    redis_client = redis.asyncio.from_url(redis_settings.url)
    
    # Initialize queue
    queue = RedisQueue(
        redis_client=redis_client,
        queue_name=settings.queue_name,
        consumer_group="document-processors",
        consumer_name=f"processor-{os.getpid()}",
        dlq_name=settings.dead_letter_queue
    )
    
    # Initialize pipeline (from ingestion service)
    from aswa_ingestion.processing.pipeline import DocumentProcessingPipeline
    # ... initialize pipeline components
    
    # Create handler
    handler = DocumentProcessingHandler(session_factory, pipeline)
    
    # Create and start worker
    worker = Worker(
        queue=queue,
        handler=handler,
        concurrency=settings.concurrency,
        batch_size=settings.batch_size,
        poll_interval=settings.poll_interval_seconds,
        max_retries=settings.max_retries
    )
    
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())

8. /workers/document-processor/tests/:
- conftest.py with fixtures
- test_queue.py - test RedisQueue operations with fakeredis
- test_worker.py - test Worker lifecycle, concurrency, shutdown
- test_handlers.py - test DocumentProcessingHandler

All tests must be async using pytest-asyncio.
Test graceful shutdown behavior.
Test retry and DLQ logic.
```