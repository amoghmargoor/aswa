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
