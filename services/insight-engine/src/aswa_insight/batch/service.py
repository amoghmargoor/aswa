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
