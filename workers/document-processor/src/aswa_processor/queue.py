"""Redis-based job queue with visibility timeout and dead letter queue.

Uses Redis Streams for reliable message delivery with consumer groups.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


@dataclass
class QueueMessage:
    """Message from the queue.

    Attributes:
        id: Redis stream message ID
        payload: Job payload dictionary
        attempts: Number of processing attempts
        created_at: When the message was created
    """

    id: str
    payload: dict[str, Any]
    attempts: int
    created_at: datetime


class RedisQueue:
    """Redis-based job queue with visibility timeout and dead letter queue.

    Uses Redis Streams for reliable message delivery with consumer groups.
    Supports:
    - Consumer groups for distributed processing
    - Message acknowledgment
    - Automatic retry with exponential backoff
    - Dead letter queue for failed messages
    - Priority and delayed messages
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        queue_name: str,
        consumer_group: str,
        consumer_name: str,
        dlq_name: str | None = None,
    ) -> None:
        """Initialize Redis queue.

        Args:
            redis_client: Async Redis client
            queue_name: Name of the Redis stream
            consumer_group: Consumer group name
            consumer_name: Unique consumer identifier
            dlq_name: Dead letter queue name
        """
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
                mkstream=True,
            )
            logger.info("Consumer group created", group=self.consumer_group)
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer group already exists")
            else:
                raise

    async def enqueue(
        self,
        payload: dict[str, Any],
        priority: int = 0,
        delay_seconds: int = 0,
    ) -> str:
        """Add job to queue.

        Args:
            payload: Job payload
            priority: Job priority (higher = more important)
            delay_seconds: Delay before processing

        Returns:
            Message ID
        """
        process_after = ""
        if delay_seconds:
            process_after = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()

        message = {
            "payload": json.dumps(payload),
            "priority": str(priority),
            "attempts": "0",
            "created_at": datetime.utcnow().isoformat(),
            "process_after": process_after,
        }

        msg_id = await self.redis.xadd(self.queue_name, message)
        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        logger.debug("Job enqueued", queue=self.queue_name, msg_id=msg_id_str)
        return msg_id_str

    async def enqueue_batch(self, payloads: list[dict[str, Any]]) -> list[str]:
        """Add multiple jobs to queue.

        Args:
            payloads: List of job payloads

        Returns:
            List of message IDs
        """
        pipe = self.redis.pipeline()
        for payload in payloads:
            message = {
                "payload": json.dumps(payload),
                "priority": "0",
                "attempts": "0",
                "created_at": datetime.utcnow().isoformat(),
                "process_after": "",
            }
            pipe.xadd(self.queue_name, message)

        results = await pipe.execute()
        return [r.decode() if isinstance(r, bytes) else r for r in results]

    async def dequeue(
        self,
        count: int = 1,
        block_ms: int = 5000,
    ) -> list[QueueMessage]:
        """Fetch pending jobs from queue.

        Uses XREADGROUP for consumer group semantics.

        Args:
            count: Maximum messages to fetch
            block_ms: Block timeout in milliseconds

        Returns:
            List of queue messages
        """
        # First, claim any pending messages that timed out
        await self._claim_stale_messages()

        # Read new messages
        messages = await self.redis.xreadgroup(
            groupname=self.consumer_group,
            consumername=self.consumer_name,
            streams={self.queue_name: ">"},
            count=count,
            block=block_ms,
        )

        result: list[QueueMessage] = []
        if messages:
            for _, stream_messages in messages:
                for msg_id, fields in stream_messages:
                    msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

                    # Check delay
                    process_after = fields.get(b"process_after", b"").decode()
                    if process_after and datetime.fromisoformat(process_after) > datetime.utcnow():
                        continue

                    result.append(
                        QueueMessage(
                            id=msg_id_str,
                            payload=json.loads(fields[b"payload"]),
                            attempts=int(fields.get(b"attempts", 0)),
                            created_at=datetime.fromisoformat(fields[b"created_at"].decode()),
                        )
                    )

        return result

    async def _claim_stale_messages(self, min_idle_ms: int = 300000) -> None:
        """Claim messages that have been pending too long.

        Args:
            min_idle_ms: Minimum idle time to consider stale (default 5 minutes)
        """
        try:
            pending = await self.redis.xpending_range(
                self.queue_name,
                self.consumer_group,
                min="-",
                max="+",
                count=100,
            )

            stale_ids = [
                p["message_id"] for p in pending if p["time_since_delivered"] > min_idle_ms
            ]

            if stale_ids:
                await self.redis.xclaim(
                    self.queue_name,
                    self.consumer_group,
                    self.consumer_name,
                    min_idle_time=min_idle_ms,
                    message_ids=stale_ids,
                )
                logger.info("Claimed stale messages", count=len(stale_ids))

        except Exception as e:
            logger.warning("Failed to claim stale messages", error=str(e))

    async def ack(self, message_id: str) -> None:
        """Acknowledge successful processing.

        Args:
            message_id: Message ID to acknowledge
        """
        await self.redis.xack(self.queue_name, self.consumer_group, message_id)
        await self.redis.xdel(self.queue_name, message_id)
        logger.debug("Message acknowledged", msg_id=message_id)

    async def nack(
        self,
        message_id: str,
        retry: bool = True,
        max_retries: int = 3,
    ) -> None:
        """Negative acknowledge - return to queue or send to DLQ.

        Args:
            message_id: Message ID to nack
            retry: Whether to retry or send directly to DLQ
            max_retries: Maximum retry attempts
        """
        # Get current message data
        messages = await self.redis.xrange(self.queue_name, message_id, message_id)
        if not messages:
            return

        _, fields = messages[0]
        attempts = int(fields.get(b"attempts", 0)) + 1

        if retry and attempts < max_retries:
            # Update attempt count and release back to queue
            # Add exponential backoff delay
            delay_seconds = 60 * attempts
            process_after = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()

            await self.redis.xadd(
                self.queue_name,
                {
                    "payload": fields[b"payload"],
                    "priority": fields.get(b"priority", b"0"),
                    "attempts": str(attempts),
                    "created_at": fields[b"created_at"],
                    "process_after": process_after,
                },
            )
            logger.info("Message requeued", msg_id=message_id, attempt=attempts)
        else:
            # Send to dead letter queue
            await self.redis.xadd(
                self.dlq_name,
                {
                    "original_id": message_id,
                    "payload": fields[b"payload"],
                    "attempts": str(attempts),
                    "failed_at": datetime.utcnow().isoformat(),
                    "created_at": fields[b"created_at"],
                },
            )
            logger.warning("Message sent to DLQ", msg_id=message_id, attempts=attempts)

        # Remove from main queue
        await self.redis.xack(self.queue_name, self.consumer_group, message_id)
        await self.redis.xdel(self.queue_name, message_id)

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue stats
        """
        try:
            info = await self.redis.xinfo_stream(self.queue_name)
            groups = await self.redis.xinfo_groups(self.queue_name)

            pending_count = 0
            for group in groups:
                group_name = group.get("name", b"")
                if isinstance(group_name, bytes):
                    group_name = group_name.decode()
                if group_name == self.consumer_group:
                    pending_count = group.get("pending", 0)

            return {
                "length": info.get("length", 0),
                "pending": pending_count,
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
            }
        except redis.ResponseError:
            # Stream doesn't exist yet
            return {"length": 0, "pending": 0, "first_entry": None, "last_entry": None}

    async def get_dlq_length(self) -> int:
        """Get dead letter queue length.

        Returns:
            Number of messages in DLQ
        """
        try:
            info = await self.redis.xinfo_stream(self.dlq_name)
            return info.get("length", 0)
        except redis.ResponseError:
            return 0

    async def reprocess_dlq(self, count: int = 10) -> int:
        """Move messages from DLQ back to main queue.

        Args:
            count: Maximum messages to reprocess

        Returns:
            Number of messages reprocessed
        """
        messages = await self.redis.xrange(self.dlq_name, count=count)
        reprocessed = 0

        for msg_id, fields in messages:
            await self.redis.xadd(
                self.queue_name,
                {
                    "payload": fields[b"payload"],
                    "priority": "0",
                    "attempts": "0",  # Reset attempts
                    "created_at": datetime.utcnow().isoformat(),
                    "process_after": "",
                },
            )
            await self.redis.xdel(self.dlq_name, msg_id)
            reprocessed += 1

        if reprocessed:
            logger.info("Reprocessed DLQ messages", count=reprocessed)

        return reprocessed
