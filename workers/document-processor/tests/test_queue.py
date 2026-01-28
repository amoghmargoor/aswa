"""Tests for RedisQueue."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import fakeredis.aioredis

from aswa_processor.queue import RedisQueue, QueueMessage


class TestRedisQueueInitialization:
    """Tests for queue initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_consumer_group(
        self, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        """Test that initialize creates consumer group."""
        queue = RedisQueue(
            redis_client=fake_redis,
            queue_name="test_init_queue",
            consumer_group="test_init_group",
            consumer_name="test_consumer",
        )

        await queue.initialize()

        # Consumer group should exist
        groups = await fake_redis.xinfo_groups("test_init_queue")
        assert len(groups) == 1
        assert groups[0]["name"] == b"test_init_group"

    @pytest.mark.asyncio
    async def test_initialize_idempotent(
        self, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        """Test that initialize can be called multiple times."""
        queue = RedisQueue(
            redis_client=fake_redis,
            queue_name="test_idempotent",
            consumer_group="test_group",
            consumer_name="test_consumer",
        )

        await queue.initialize()
        await queue.initialize()  # Should not raise

        groups = await fake_redis.xinfo_groups("test_idempotent")
        assert len(groups) == 1


class TestRedisQueueEnqueue:
    """Tests for enqueue operations."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_message(self, redis_queue: RedisQueue) -> None:
        """Test basic enqueue."""
        payload = {"document_id": "123", "tenant_id": "456"}

        msg_id = await redis_queue.enqueue(payload)

        assert msg_id is not None
        stats = await redis_queue.get_queue_stats()
        assert stats["length"] == 1

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, redis_queue: RedisQueue) -> None:
        """Test enqueue with priority."""
        payload = {"task": "important"}

        msg_id = await redis_queue.enqueue(payload, priority=10)

        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_enqueue_with_delay(self, redis_queue: RedisQueue) -> None:
        """Test enqueue with delay."""
        payload = {"task": "delayed"}

        msg_id = await redis_queue.enqueue(payload, delay_seconds=60)

        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, redis_queue: RedisQueue) -> None:
        """Test batch enqueue."""
        payloads = [
            {"document_id": "1"},
            {"document_id": "2"},
            {"document_id": "3"},
        ]

        msg_ids = await redis_queue.enqueue_batch(payloads)

        assert len(msg_ids) == 3
        stats = await redis_queue.get_queue_stats()
        assert stats["length"] == 3


class TestRedisQueueDequeue:
    """Tests for dequeue operations."""

    @pytest.mark.asyncio
    async def test_dequeue_returns_messages(self, redis_queue: RedisQueue) -> None:
        """Test basic dequeue."""
        payload = {"document_id": "123"}
        await redis_queue.enqueue(payload)

        messages = await redis_queue.dequeue(count=1, block_ms=100)

        assert len(messages) == 1
        assert messages[0].payload == payload
        assert messages[0].attempts == 0

    @pytest.mark.asyncio
    async def test_dequeue_respects_count(self, redis_queue: RedisQueue) -> None:
        """Test dequeue respects count limit."""
        for i in range(5):
            await redis_queue.enqueue({"id": i})

        messages = await redis_queue.dequeue(count=3, block_ms=100)

        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, redis_queue: RedisQueue) -> None:
        """Test dequeue on empty queue."""
        messages = await redis_queue.dequeue(count=1, block_ms=100)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_dequeue_skips_delayed_messages(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test that delayed messages are skipped."""
        await redis_queue.enqueue({"task": "delayed"}, delay_seconds=3600)

        messages = await redis_queue.dequeue(count=1, block_ms=100)

        # Should be empty because message is delayed
        assert len(messages) == 0


class TestRedisQueueAcknowledge:
    """Tests for message acknowledgment."""

    @pytest.mark.asyncio
    async def test_ack_removes_message(self, redis_queue: RedisQueue) -> None:
        """Test that ack removes message from queue."""
        await redis_queue.enqueue({"task": "test"})
        messages = await redis_queue.dequeue(count=1, block_ms=100)

        await redis_queue.ack(messages[0].id)

        stats = await redis_queue.get_queue_stats()
        assert stats["length"] == 0

    @pytest.mark.asyncio
    async def test_nack_with_retry(self, redis_queue: RedisQueue) -> None:
        """Test nack requeues message."""
        await redis_queue.enqueue({"task": "test"})
        messages = await redis_queue.dequeue(count=1, block_ms=100)
        original_id = messages[0].id

        await redis_queue.nack(original_id, retry=True, max_retries=3)

        # Should have a new message with incremented attempts
        stats = await redis_queue.get_queue_stats()
        assert stats["length"] == 1

    @pytest.mark.asyncio
    async def test_nack_exceeds_retries_goes_to_dlq(
        self, redis_queue: RedisQueue
    ) -> None:
        """Test that message goes to DLQ after max retries."""
        await redis_queue.enqueue({"task": "failing"})

        # Simulate multiple failures
        for _ in range(3):
            messages = await redis_queue.dequeue(count=1, block_ms=100)
            if messages:
                await redis_queue.nack(messages[0].id, retry=True, max_retries=3)

        # After 3 attempts, next should go to DLQ
        messages = await redis_queue.dequeue(count=1, block_ms=100)
        if messages:
            await redis_queue.nack(messages[0].id, retry=True, max_retries=3)

        dlq_length = await redis_queue.get_dlq_length()
        assert dlq_length >= 1

    @pytest.mark.asyncio
    async def test_nack_no_retry_goes_to_dlq(self, redis_queue: RedisQueue) -> None:
        """Test nack without retry goes directly to DLQ."""
        await redis_queue.enqueue({"task": "test"})
        messages = await redis_queue.dequeue(count=1, block_ms=100)

        await redis_queue.nack(messages[0].id, retry=False)

        dlq_length = await redis_queue.get_dlq_length()
        assert dlq_length == 1


class TestRedisQueueStats:
    """Tests for queue statistics."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, redis_queue: RedisQueue) -> None:
        """Test getting queue stats."""
        for i in range(5):
            await redis_queue.enqueue({"id": i})

        stats = await redis_queue.get_queue_stats()

        assert stats["length"] == 5
        assert "pending" in stats

    @pytest.mark.asyncio
    async def test_get_dlq_length(self, redis_queue: RedisQueue) -> None:
        """Test getting DLQ length."""
        length = await redis_queue.get_dlq_length()
        assert length == 0


class TestRedisQueueDLQReprocessing:
    """Tests for DLQ reprocessing."""

    @pytest.mark.asyncio
    async def test_reprocess_dlq(self, redis_queue: RedisQueue) -> None:
        """Test reprocessing messages from DLQ."""
        # Add message and send to DLQ
        await redis_queue.enqueue({"task": "test"})
        messages = await redis_queue.dequeue(count=1, block_ms=100)
        await redis_queue.nack(messages[0].id, retry=False)

        assert await redis_queue.get_dlq_length() == 1

        # Reprocess
        count = await redis_queue.reprocess_dlq(count=10)

        assert count == 1
        assert await redis_queue.get_dlq_length() == 0
        stats = await redis_queue.get_queue_stats()
        assert stats["length"] == 1
