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
