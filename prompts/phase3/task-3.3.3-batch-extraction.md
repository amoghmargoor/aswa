# Task 3.3.3: Batch Extraction Service

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The extraction pipeline components are implemented:
- Structured extraction at `/services/insight-engine/src/aswa_insight/extraction/`
- Map-reduce for long documents at `/services/insight-engine/src/aswa_insight/extraction/mapreduce.py`
- Chunking at `/services/insight-engine/src/aswa_insight/chunking/`

## Objective

Create a batch extraction service that can:
1. Process multiple documents concurrently
2. Manage extraction job queues
3. Track progress and handle failures
4. Support priority-based processing
5. Provide status updates and metrics

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/batch/__init__.py`
```python
from .job import ExtractionJob, JobStatus, JobPriority
from .queue import JobQueue, InMemoryJobQueue, RedisJobQueue
from .service import BatchExtractionService
from .progress import ProgressTracker, JobProgress

__all__ = [
    "ExtractionJob",
    "JobStatus",
    "JobPriority",
    "JobQueue",
    "InMemoryJobQueue",
    "RedisJobQueue",
    "BatchExtractionService",
    "ProgressTracker",
    "JobProgress",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/batch/job.py`
Job definitions and status tracking:

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of an extraction job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class JobPriority(IntEnum):
    """Priority levels for jobs."""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class ExtractionJob(BaseModel):
    """An extraction job to be processed."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    document_ids: list[UUID]
    extraction_types: list[str] = Field(default=["entity", "risk", "opportunity", "pattern"])
    priority: JobPriority = JobPriority.NORMAL
    context: dict[str, Any] = Field(default_factory=dict)

    # Status tracking
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Progress tracking
    total_documents: int = 0
    processed_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0

    # Results
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    # Options
    force_reextract: bool = False
    callback_url: str | None = None
    max_retries: int = 3

    def __post_init__(self):
        if self.total_documents == 0:
            self.total_documents = len(self.document_ids)

    @property
    def progress_percentage(self) -> float:
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100

    @property
    def is_complete(self) -> bool:
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.PARTIALLY_COMPLETED,
        ]

    @property
    def duration_seconds(self) -> float | None:
        if not self.started_at:
            return None
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def start(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self) -> None:
        """Mark job as completed."""
        self.completed_at = datetime.utcnow()
        if self.failed_documents == 0:
            self.status = JobStatus.COMPLETED
        elif self.successful_documents > 0:
            self.status = JobStatus.PARTIALLY_COMPLETED
        else:
            self.status = JobStatus.FAILED

    def fail(self, error: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.errors.append(error)

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def add_document_result(self, document_id: UUID, success: bool, result: Any = None, error: str | None = None) -> None:
        """Add result for a processed document."""
        self.processed_documents += 1
        if success:
            self.successful_documents += 1
            if result:
                self.results[str(document_id)] = result
        else:
            self.failed_documents += 1
            if error:
                self.errors.append(f"{document_id}: {error}")


class JobSummary(BaseModel):
    """Summary of a job for API responses."""
    id: UUID
    tenant_id: UUID
    status: JobStatus
    priority: JobPriority
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    progress_percentage: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None

    @classmethod
    def from_job(cls, job: ExtractionJob) -> "JobSummary":
        return cls(
            id=job.id,
            tenant_id=job.tenant_id,
            status=job.status,
            priority=job.priority,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            successful_documents=job.successful_documents,
            failed_documents=job.failed_documents,
            progress_percentage=job.progress_percentage,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
        )
```

### 3. Create `/services/insight-engine/src/aswa_insight/batch/queue.py`
Job queue implementations:

```python
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID
import heapq
import structlog

from .job import ExtractionJob, JobStatus, JobPriority

logger = structlog.get_logger()


class JobQueue(ABC):
    """Abstract job queue interface."""

    @abstractmethod
    async def enqueue(self, job: ExtractionJob) -> None:
        """Add job to queue."""
        ...

    @abstractmethod
    async def dequeue(self) -> ExtractionJob | None:
        """Get next job from queue."""
        ...

    @abstractmethod
    async def get_job(self, job_id: UUID) -> ExtractionJob | None:
        """Get job by ID."""
        ...

    @abstractmethod
    async def update_job(self, job: ExtractionJob) -> None:
        """Update job state."""
        ...

    @abstractmethod
    async def list_jobs(
        self,
        tenant_id: UUID | None = None,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[ExtractionJob]:
        """List jobs with optional filters."""
        ...

    @abstractmethod
    async def queue_size(self) -> int:
        """Get number of pending jobs."""
        ...


class InMemoryJobQueue(JobQueue):
    """In-memory job queue for development/testing."""

    def __init__(self):
        self._jobs: dict[UUID, ExtractionJob] = {}
        self._queue: list[tuple[int, datetime, UUID]] = []  # (priority, created_at, job_id)
        self._lock = asyncio.Lock()

    async def enqueue(self, job: ExtractionJob) -> None:
        async with self._lock:
            self._jobs[job.id] = job
            job.status = JobStatus.QUEUED

            # Use negative priority for max-heap behavior
            heapq.heappush(
                self._queue,
                (-job.priority, job.created_at, job.id)
            )

            logger.info(
                "Job enqueued",
                job_id=str(job.id),
                priority=job.priority,
                documents=job.total_documents,
            )

    async def dequeue(self) -> ExtractionJob | None:
        async with self._lock:
            while self._queue:
                _, _, job_id = heapq.heappop(self._queue)
                job = self._jobs.get(job_id)

                if job and job.status == JobStatus.QUEUED:
                    return job

            return None

    async def get_job(self, job_id: UUID) -> ExtractionJob | None:
        return self._jobs.get(job_id)

    async def update_job(self, job: ExtractionJob) -> None:
        async with self._lock:
            self._jobs[job.id] = job

    async def list_jobs(
        self,
        tenant_id: UUID | None = None,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[ExtractionJob]:
        jobs = list(self._jobs.values())

        if tenant_id:
            jobs = [j for j in jobs if j.tenant_id == tenant_id]

        if status:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    async def queue_size(self) -> int:
        return len([j for j in self._jobs.values() if j.status == JobStatus.QUEUED])

    async def clear(self) -> None:
        """Clear all jobs (for testing)."""
        async with self._lock:
            self._jobs.clear()
            self._queue.clear()


class RedisJobQueue(JobQueue):
    """Redis-backed job queue for production."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        queue_name: str = "extraction_jobs",
        job_prefix: str = "job:",
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.job_prefix = job_prefix
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def enqueue(self, job: ExtractionJob) -> None:
        client = await self._get_client()
        job.status = JobStatus.QUEUED

        # Store job data
        job_key = f"{self.job_prefix}{job.id}"
        await client.set(job_key, job.model_dump_json())

        # Add to sorted set with priority as score
        # Higher priority = higher score = processed first
        score = job.priority * 1000000 - job.created_at.timestamp()
        await client.zadd(self.queue_name, {str(job.id): score})

        logger.info(
            "Job enqueued to Redis",
            job_id=str(job.id),
            priority=job.priority,
        )

    async def dequeue(self) -> ExtractionJob | None:
        client = await self._get_client()

        # Get highest priority job
        result = await client.zpopmax(self.queue_name)
        if not result:
            return None

        job_id = result[0][0].decode() if isinstance(result[0][0], bytes) else result[0][0]
        job_key = f"{self.job_prefix}{job_id}"

        job_data = await client.get(job_key)
        if not job_data:
            return None

        return ExtractionJob.model_validate_json(job_data)

    async def get_job(self, job_id: UUID) -> ExtractionJob | None:
        client = await self._get_client()
        job_key = f"{self.job_prefix}{job_id}"

        job_data = await client.get(job_key)
        if not job_data:
            return None

        return ExtractionJob.model_validate_json(job_data)

    async def update_job(self, job: ExtractionJob) -> None:
        client = await self._get_client()
        job_key = f"{self.job_prefix}{job.id}"
        await client.set(job_key, job.model_dump_json())

    async def list_jobs(
        self,
        tenant_id: UUID | None = None,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[ExtractionJob]:
        client = await self._get_client()

        # Get all job keys
        cursor = 0
        jobs = []
        pattern = f"{self.job_prefix}*"

        while True:
            cursor, keys = await client.scan(cursor, match=pattern, count=100)
            for key in keys:
                job_data = await client.get(key)
                if job_data:
                    job = ExtractionJob.model_validate_json(job_data)

                    if tenant_id and job.tenant_id != tenant_id:
                        continue
                    if status and job.status != status:
                        continue

                    jobs.append(job)

            if cursor == 0:
                break

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def queue_size(self) -> int:
        client = await self._get_client()
        return await client.zcard(self.queue_name)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
```

### 4. Create `/services/insight-engine/src/aswa_insight/batch/progress.py`
Progress tracking:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any
from uuid import UUID
import asyncio
import structlog

from .job import ExtractionJob, JobStatus

logger = structlog.get_logger()


@dataclass
class JobProgress:
    """Progress information for a job."""
    job_id: UUID
    status: JobStatus
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    progress_percentage: float
    current_document: UUID | None = None
    eta_seconds: float | None = None
    messages: list[str] = field(default_factory=list)


class ProgressTracker:
    """Track and report job progress."""

    def __init__(
        self,
        callback: Callable[[JobProgress], Any] | None = None,
        update_interval_seconds: float = 1.0,
    ):
        self.callback = callback
        self.update_interval = update_interval_seconds
        self._progress_cache: dict[UUID, JobProgress] = {}
        self._last_update: dict[UUID, datetime] = {}
        self._start_times: dict[UUID, datetime] = {}
        self._lock = asyncio.Lock()

    async def start_job(self, job: ExtractionJob) -> None:
        """Record job start."""
        async with self._lock:
            self._start_times[job.id] = datetime.utcnow()
            progress = self._create_progress(job)
            self._progress_cache[job.id] = progress
            await self._emit_progress(progress)

    async def update_progress(
        self,
        job: ExtractionJob,
        current_document: UUID | None = None,
        message: str | None = None,
    ) -> None:
        """Update job progress."""
        async with self._lock:
            progress = self._create_progress(job, current_document)

            if message:
                progress.messages.append(message)

            # Calculate ETA
            progress.eta_seconds = self._calculate_eta(job)

            self._progress_cache[job.id] = progress

            # Throttle updates
            last = self._last_update.get(job.id)
            now = datetime.utcnow()
            if last and (now - last).total_seconds() < self.update_interval:
                return

            self._last_update[job.id] = now
            await self._emit_progress(progress)

    async def complete_job(self, job: ExtractionJob) -> None:
        """Record job completion."""
        async with self._lock:
            progress = self._create_progress(job)
            self._progress_cache[job.id] = progress
            await self._emit_progress(progress)

            # Cleanup
            self._start_times.pop(job.id, None)

    def get_progress(self, job_id: UUID) -> JobProgress | None:
        """Get current progress for a job."""
        return self._progress_cache.get(job_id)

    def _create_progress(
        self,
        job: ExtractionJob,
        current_document: UUID | None = None,
    ) -> JobProgress:
        """Create progress object from job."""
        return JobProgress(
            job_id=job.id,
            status=job.status,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            successful_documents=job.successful_documents,
            failed_documents=job.failed_documents,
            progress_percentage=job.progress_percentage,
            current_document=current_document,
        )

    def _calculate_eta(self, job: ExtractionJob) -> float | None:
        """Calculate estimated time remaining."""
        start_time = self._start_times.get(job.id)
        if not start_time or job.processed_documents == 0:
            return None

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        docs_per_second = job.processed_documents / elapsed
        remaining_docs = job.total_documents - job.processed_documents

        if docs_per_second > 0:
            return remaining_docs / docs_per_second
        return None

    async def _emit_progress(self, progress: JobProgress) -> None:
        """Emit progress update via callback."""
        if self.callback:
            try:
                result = self.callback(progress)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Progress callback failed", error=str(e))
```

### 5. Create `/services/insight-engine/src/aswa_insight/batch/service.py`
Batch extraction service:

```python
import asyncio
from typing import Any, Callable
from uuid import UUID
import structlog

from aswa_insight.extraction.extractor import StructuredExtractor
from aswa_insight.extraction.mapreduce import MapReduceExtractor
from aswa_insight.extraction.processor import ExtractionProcessor, ProcessingResult
from aswa_insight.models.insights import Insight

from .job import ExtractionJob, JobStatus, JobPriority, JobSummary
from .queue import JobQueue, InMemoryJobQueue
from .progress import ProgressTracker, JobProgress

logger = structlog.get_logger()


class BatchExtractionService:
    """Service for batch document extraction."""

    def __init__(
        self,
        processor: ExtractionProcessor,
        job_queue: JobQueue | None = None,
        progress_tracker: ProgressTracker | None = None,
        max_concurrent_jobs: int = 3,
        max_concurrent_documents: int = 5,
        document_fetcher: Callable[[UUID], str] | None = None,
    ):
        """Initialize batch extraction service.

        Args:
            processor: Extraction processor to use
            job_queue: Job queue (default: in-memory)
            progress_tracker: Progress tracker
            max_concurrent_jobs: Max concurrent jobs
            max_concurrent_documents: Max concurrent documents per job
            document_fetcher: Function to fetch document text by ID
        """
        self.processor = processor
        self.queue = job_queue or InMemoryJobQueue()
        self.progress = progress_tracker or ProgressTracker()
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_concurrent_documents = max_concurrent_documents
        self.document_fetcher = document_fetcher

        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._job_semaphore = asyncio.Semaphore(max_concurrent_jobs)

    async def create_job(
        self,
        tenant_id: UUID,
        document_ids: list[UUID],
        extraction_types: list[str] | None = None,
        priority: JobPriority = JobPriority.NORMAL,
        context: dict[str, Any] | None = None,
        force_reextract: bool = False,
        callback_url: str | None = None,
    ) -> ExtractionJob:
        """Create and enqueue an extraction job.

        Args:
            tenant_id: Tenant ID
            document_ids: List of document IDs to process
            extraction_types: Types of extraction to perform
            priority: Job priority
            context: Extraction context
            force_reextract: Force re-extraction of existing insights
            callback_url: URL to call on completion

        Returns:
            Created job
        """
        job = ExtractionJob(
            tenant_id=tenant_id,
            document_ids=document_ids,
            extraction_types=extraction_types or ["entity", "risk", "opportunity", "pattern"],
            priority=priority,
            context=context or {},
            force_reextract=force_reextract,
            callback_url=callback_url,
            total_documents=len(document_ids),
        )

        await self.queue.enqueue(job)

        logger.info(
            "Extraction job created",
            job_id=str(job.id),
            tenant_id=str(tenant_id),
            documents=len(document_ids),
            priority=priority,
        )

        return job

    async def get_job(self, job_id: UUID, tenant_id: UUID) -> ExtractionJob | None:
        """Get job by ID (with tenant isolation)."""
        job = await self.queue.get_job(job_id)
        if job and job.tenant_id == tenant_id:
            return job
        return None

    async def get_job_summary(self, job_id: UUID, tenant_id: UUID) -> JobSummary | None:
        """Get job summary by ID."""
        job = await self.get_job(job_id, tenant_id)
        if job:
            return JobSummary.from_job(job)
        return None

    async def list_jobs(
        self,
        tenant_id: UUID,
        status: JobStatus | None = None,
        limit: int = 100,
    ) -> list[JobSummary]:
        """List jobs for a tenant."""
        jobs = await self.queue.list_jobs(tenant_id=tenant_id, status=status, limit=limit)
        return [JobSummary.from_job(j) for j in jobs]

    async def cancel_job(self, job_id: UUID, tenant_id: UUID) -> bool:
        """Cancel a job."""
        job = await self.get_job(job_id, tenant_id)
        if not job:
            return False

        if job.is_complete:
            return False

        job.cancel()
        await self.queue.update_job(job)

        logger.info("Job cancelled", job_id=str(job_id))
        return True

    async def get_job_progress(self, job_id: UUID) -> JobProgress | None:
        """Get job progress."""
        return self.progress.get_progress(job_id)

    async def start_worker(self) -> None:
        """Start the background worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Batch extraction worker started")

    async def stop_worker(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Batch extraction worker stopped")

    async def _worker_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                job = await self.queue.dequeue()
                if job:
                    asyncio.create_task(self._process_job(job))
                else:
                    await asyncio.sleep(1.0)  # No jobs, wait before checking again
            except Exception as e:
                logger.error("Worker loop error", error=str(e))
                await asyncio.sleep(5.0)

    async def _process_job(self, job: ExtractionJob) -> None:
        """Process a single job."""
        async with self._job_semaphore:
            logger.info("Processing job", job_id=str(job.id))

            job.start()
            await self.queue.update_job(job)
            await self.progress.start_job(job)

            try:
                # Process documents concurrently
                semaphore = asyncio.Semaphore(self.max_concurrent_documents)

                async def process_document(doc_id: UUID) -> tuple[UUID, bool, Any, str | None]:
                    async with semaphore:
                        # Check if job was cancelled
                        current_job = await self.queue.get_job(job.id)
                        if current_job and current_job.status == JobStatus.CANCELLED:
                            return doc_id, False, None, "Job cancelled"

                        try:
                            text = await self._fetch_document(doc_id)
                            if not text:
                                return doc_id, False, None, "Document not found"

                            result = await self.processor.process_document(
                                document_id=doc_id,
                                tenant_id=job.tenant_id,
                                text=text,
                                context=job.context,
                                extraction_types=job.extraction_types,
                            )

                            return doc_id, result.success, result, None

                        except Exception as e:
                            logger.error(
                                "Document processing failed",
                                document_id=str(doc_id),
                                error=str(e),
                            )
                            return doc_id, False, None, str(e)

                tasks = [process_document(doc_id) for doc_id in job.document_ids]

                for coro in asyncio.as_completed(tasks):
                    doc_id, success, result, error = await coro
                    job.add_document_result(doc_id, success, result, error)
                    await self.queue.update_job(job)
                    await self.progress.update_progress(job, current_document=doc_id)

                job.complete()

            except Exception as e:
                job.fail(str(e))
                logger.error("Job failed", job_id=str(job.id), error=str(e))

            await self.queue.update_job(job)
            await self.progress.complete_job(job)

            # Call webhook if configured
            if job.callback_url:
                await self._send_callback(job)

            logger.info(
                "Job completed",
                job_id=str(job.id),
                status=job.status,
                successful=job.successful_documents,
                failed=job.failed_documents,
            )

    async def _fetch_document(self, document_id: UUID) -> str | None:
        """Fetch document text."""
        if self.document_fetcher:
            result = self.document_fetcher(document_id)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return None

    async def _send_callback(self, job: ExtractionJob) -> None:
        """Send completion callback."""
        if not job.callback_url:
            return

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(
                    job.callback_url,
                    json={
                        "job_id": str(job.id),
                        "status": job.status.value,
                        "total_documents": job.total_documents,
                        "successful_documents": job.successful_documents,
                        "failed_documents": job.failed_documents,
                    },
                    timeout=30.0,
                )
        except Exception as e:
            logger.error("Callback failed", url=job.callback_url, error=str(e))

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics."""
        return {
            "running": self._running,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "max_concurrent_documents": self.max_concurrent_documents,
        }
```

## Test Requirements

### Create `/services/insight-engine/tests/batch/__init__.py`

### Create `/services/insight-engine/tests/batch/test_job.py`
```python
import pytest
from uuid import uuid4
from datetime import datetime

from aswa_insight.batch.job import ExtractionJob, JobStatus, JobPriority, JobSummary


class TestExtractionJob:
    def test_create_job(self):
        """Test job creation."""
        job = ExtractionJob(
            tenant_id=uuid4(),
            document_ids=[uuid4(), uuid4()],
        )
        assert job.status == JobStatus.PENDING
        assert job.total_documents == 2
        assert job.progress_percentage == 0.0

    def test_job_start(self):
        """Test starting a job."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    def test_job_complete_success(self):
        """Test successful completion."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=True, result={"test": "data"})
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.successful_documents == 1

    def test_job_complete_partial(self):
        """Test partial completion."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4(), uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=True)
        job.add_document_result(job.document_ids[1], success=False, error="Failed")
        job.complete()
        assert job.status == JobStatus.PARTIALLY_COMPLETED

    def test_job_complete_all_failed(self):
        """Test all documents failed."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=False, error="Failed")
        job.complete()
        assert job.status == JobStatus.FAILED

    def test_job_cancel(self):
        """Test job cancellation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.cancel()
        assert job.status == JobStatus.CANCELLED
        assert job.is_complete

    def test_progress_percentage(self):
        """Test progress calculation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()] * 4)
        job.processed_documents = 2
        assert job.progress_percentage == 50.0

    def test_duration_calculation(self):
        """Test duration calculation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        # Duration should be calculable
        assert job.duration_seconds is not None


class TestJobSummary:
    def test_from_job(self):
        """Test creating summary from job."""
        job = ExtractionJob(
            tenant_id=uuid4(),
            document_ids=[uuid4()],
            priority=JobPriority.HIGH,
        )
        summary = JobSummary.from_job(job)
        assert summary.id == job.id
        assert summary.priority == JobPriority.HIGH
```

### Create `/services/insight-engine/tests/batch/test_queue.py`
```python
import pytest
from uuid import uuid4

from aswa_insight.batch.job import ExtractionJob, JobStatus, JobPriority
from aswa_insight.batch.queue import InMemoryJobQueue


class TestInMemoryJobQueue:
    @pytest.fixture
    def queue(self):
        return InMemoryJobQueue()

    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self, queue):
        """Test basic enqueue/dequeue."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        await queue.enqueue(job)

        assert await queue.queue_size() == 1

        dequeued = await queue.dequeue()
        assert dequeued is not None
        assert dequeued.id == job.id

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Test priority-based ordering."""
        low = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()], priority=JobPriority.LOW)
        high = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()], priority=JobPriority.HIGH)

        await queue.enqueue(low)
        await queue.enqueue(high)

        first = await queue.dequeue()
        assert first.priority == JobPriority.HIGH

    @pytest.mark.asyncio
    async def test_get_job(self, queue):
        """Test getting job by ID."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        await queue.enqueue(job)

        retrieved = await queue.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    @pytest.mark.asyncio
    async def test_update_job(self, queue):
        """Test updating job."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        await queue.enqueue(job)

        job.start()
        await queue.update_job(job)

        retrieved = await queue.get_job(job.id)
        assert retrieved.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_jobs_by_tenant(self, queue):
        """Test listing jobs by tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        await queue.enqueue(ExtractionJob(tenant_id=tenant1, document_ids=[uuid4()]))
        await queue.enqueue(ExtractionJob(tenant_id=tenant2, document_ids=[uuid4()]))
        await queue.enqueue(ExtractionJob(tenant_id=tenant1, document_ids=[uuid4()]))

        jobs = await queue.list_jobs(tenant_id=tenant1)
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, queue):
        """Test listing jobs by status."""
        job1 = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job2 = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])

        await queue.enqueue(job1)
        await queue.enqueue(job2)

        # Complete one
        job1.complete()
        await queue.update_job(job1)

        queued = await queue.list_jobs(status=JobStatus.QUEUED)
        assert len(queued) == 1
```

### Create `/services/insight-engine/tests/batch/test_service.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.batch.service import BatchExtractionService
from aswa_insight.batch.job import JobPriority, JobStatus
from aswa_insight.extraction.processor import ExtractionProcessor, ProcessingResult


class TestBatchExtractionService:
    @pytest.fixture
    def mock_processor(self):
        processor = MagicMock(spec=ExtractionProcessor)
        processor.process_document = AsyncMock(return_value=ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={},
            validation_results={},
            insights=[],
        ))
        return processor

    @pytest.fixture
    def service(self, mock_processor):
        return BatchExtractionService(
            processor=mock_processor,
            document_fetcher=lambda doc_id: "Test document content",
        )

    @pytest.mark.asyncio
    async def test_create_job(self, service):
        """Test creating extraction job."""
        tenant_id = uuid4()
        doc_ids = [uuid4(), uuid4()]

        job = await service.create_job(
            tenant_id=tenant_id,
            document_ids=doc_ids,
        )

        assert job.tenant_id == tenant_id
        assert job.total_documents == 2
        assert job.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_get_job_tenant_isolation(self, service):
        """Test tenant isolation when getting jobs."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        job = await service.create_job(
            tenant_id=tenant1,
            document_ids=[uuid4()],
        )

        # Same tenant can access
        retrieved = await service.get_job(job.id, tenant1)
        assert retrieved is not None

        # Different tenant cannot
        retrieved = await service.get_job(job.id, tenant2)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cancel_job(self, service):
        """Test job cancellation."""
        tenant_id = uuid4()
        job = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
        )

        success = await service.cancel_job(job.id, tenant_id)
        assert success is True

        cancelled = await service.get_job(job.id, tenant_id)
        assert cancelled.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_list_jobs(self, service):
        """Test listing jobs."""
        tenant_id = uuid4()

        await service.create_job(tenant_id=tenant_id, document_ids=[uuid4()])
        await service.create_job(tenant_id=tenant_id, document_ids=[uuid4()])

        jobs = await service.list_jobs(tenant_id)
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_priority_handling(self, service):
        """Test jobs with different priorities."""
        tenant_id = uuid4()

        low = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
            priority=JobPriority.LOW,
        )
        high = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
            priority=JobPriority.HIGH,
        )

        assert high.priority > low.priority


class TestBatchExtractionWorker:
    @pytest.mark.asyncio
    async def test_worker_start_stop(self, mock_processor):
        """Test worker lifecycle."""
        service = BatchExtractionService(processor=mock_processor)

        await service.start_worker()
        assert service._running is True

        await service.stop_worker()
        assert service._running is False
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/batch/ -v`
2. Verify imports: `python -c "from aswa_insight.batch import *"`
3. Test job creation and processing flow
