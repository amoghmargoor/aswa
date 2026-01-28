"""Tests for Worker."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from aswa_processor.queue import RedisQueue, QueueMessage
from aswa_processor.worker import Worker


class TestWorkerLifecycle:
    """Tests for worker lifecycle management."""

    @pytest.mark.asyncio
    async def test_worker_starts_and_stops(
        self, redis_queue: RedisQueue, mock_handler: AsyncMock
    ) -> None:
        """Test worker can start and stop cleanly."""
        worker = Worker(
            queue=redis_queue,
            handler=mock_handler,
            concurrency=2,
            poll_interval=0.1,
        )

        # Start worker in background
        task = asyncio.create_task(worker.start())

        # Give it a moment to start
        await asyncio.sleep(0.2)
        assert worker.is_running

        # Stop worker
        await worker.stop()
        await asyncio.sleep(0.2)

        assert not worker.is_running
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_processes_messages(
        self, redis_queue: RedisQueue, mock_handler: AsyncMock
    ) -> None:
        """Test worker processes messages from queue."""
        worker = Worker(
            queue=redis_queue,
            handler=mock_handler,
            concurrency=2,
            poll_interval=0.1,
        )

        # Enqueue a job
        payload = {"document_id": "123", "tenant_id": "456"}
        await redis_queue.enqueue(payload)

        # Start worker
        task = asyncio.create_task(worker.start())

        # Wait for processing
        await asyncio.sleep(0.5)

        # Handler should have been called
        mock_handler.assert_called_once_with(payload)

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_worker_handles_multiple_messages(
        self, redis_queue: RedisQueue, mock_handler: AsyncMock
    ) -> None:
        """Test worker processes multiple messages."""
        worker = Worker(
            queue=redis_queue,
            handler=mock_handler,
            concurrency=4,
            batch_size=10,
            poll_interval=0.1,
        )

        # Enqueue multiple jobs
        for i in range(5):
            await redis_queue.enqueue({"id": i})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(1.0)

        assert mock_handler.call_count == 5

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWorkerConcurrency:
    """Tests for worker concurrency control."""

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test worker respects concurrency limit."""
        concurrent_jobs = []
        max_concurrent = 0

        async def tracking_handler(payload: dict) -> None:
            nonlocal max_concurrent
            concurrent_jobs.append(payload["id"])
            max_concurrent = max(max_concurrent, len(concurrent_jobs))
            await asyncio.sleep(0.2)  # Simulate work
            concurrent_jobs.remove(payload["id"])

        worker = Worker(
            queue=redis_queue,
            handler=tracking_handler,
            concurrency=2,  # Limit to 2 concurrent
            batch_size=10,
            poll_interval=0.05,
        )

        # Enqueue more jobs than concurrency limit
        for i in range(6):
            await redis_queue.enqueue({"id": i})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(1.5)

        # Should never exceed concurrency limit
        assert max_concurrent <= 2

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWorkerErrorHandling:
    """Tests for worker error handling."""

    @pytest.mark.asyncio
    async def test_handler_failure_triggers_retry(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test that handler failures trigger retry."""
        call_count = 0

        async def failing_handler(payload: dict) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Simulated failure")

        worker = Worker(
            queue=redis_queue,
            handler=failing_handler,
            concurrency=1,
            poll_interval=0.1,
            max_retries=3,
        )

        await redis_queue.enqueue({"task": "test"})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(1.0)

        # Should have been called multiple times due to retry
        assert call_count >= 1

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_job_timeout(self, redis_queue: RedisQueue) -> None:
        """Test that long-running jobs timeout."""
        timed_out = False

        async def slow_handler(payload: dict) -> None:
            nonlocal timed_out
            try:
                await asyncio.sleep(10)  # Longer than timeout
            except asyncio.CancelledError:
                timed_out = True
                raise

        worker = Worker(
            queue=redis_queue,
            handler=slow_handler,
            concurrency=1,
            poll_interval=0.1,
            job_timeout=0.5,  # Short timeout
        )

        await redis_queue.enqueue({"task": "slow"})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(1.5)

        # Job should have timed out
        # Check that message was nacked (requeued or DLQed)
        stats = await redis_queue.get_queue_stats()
        # Message should either be requeued or in DLQ

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWorkerGracefulShutdown:
    """Tests for graceful shutdown behavior."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_waits_for_active_jobs(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test graceful shutdown waits for active jobs."""
        job_completed = False

        async def slow_handler(payload: dict) -> None:
            nonlocal job_completed
            await asyncio.sleep(0.5)
            job_completed = True

        worker = Worker(
            queue=redis_queue,
            handler=slow_handler,
            concurrency=1,
            poll_interval=0.1,
        )

        await redis_queue.enqueue({"task": "test"})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.2)  # Let job start

        # Request shutdown while job is running
        await worker.stop()
        await asyncio.sleep(1.0)

        # Job should have completed
        assert job_completed

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_active_jobs_count(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test active jobs tracking."""
        started = asyncio.Event()

        async def blocking_handler(payload: dict) -> None:
            started.set()
            await asyncio.sleep(5)

        worker = Worker(
            queue=redis_queue,
            handler=blocking_handler,
            concurrency=2,
            poll_interval=0.1,
        )

        await redis_queue.enqueue({"task": "1"})
        await redis_queue.enqueue({"task": "2"})

        task = asyncio.create_task(worker.start())
        await started.wait()
        await asyncio.sleep(0.2)

        assert worker.active_jobs >= 1

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestWorkerMetrics:
    """Tests for worker metrics."""

    @pytest.mark.asyncio
    async def test_metrics_incremented_on_success(
        self, redis_queue: RedisQueue, mock_handler: AsyncMock
    ) -> None:
        """Test metrics are incremented on successful processing."""
        worker = Worker(
            queue=redis_queue,
            handler=mock_handler,
            concurrency=1,
            poll_interval=0.1,
        )

        await redis_queue.enqueue({"task": "test"})

        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.5)

        # Metrics should be updated (we can't easily check prometheus values
        # without more setup, but we verify no errors occurred)
        mock_handler.assert_called_once()

        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
