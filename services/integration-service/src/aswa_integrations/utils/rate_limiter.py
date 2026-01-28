import asyncio
from datetime import datetime, timedelta
from typing import Callable, Awaitable
import redis.asyncio as redis
import structlog

from aswa_integrations.config import get_settings

logger = structlog.get_logger()


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = "ratelimit",
    ):
        self.settings = get_settings()
        self.redis = redis_client
        self.key_prefix = key_prefix

    async def is_allowed(
        self,
        identifier: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, dict]:
        """Check if a request is allowed under rate limits.

        Args:
            identifier: Unique identifier for the rate limit bucket
            limit: Maximum requests per window (defaults to settings)
            window: Window size in seconds (defaults to settings)

        Returns:
            Tuple of (is_allowed, metadata)
        """
        limit = limit or self.settings.default_rate_limit
        window = window or self.settings.rate_limit_window

        key = f"{self.key_prefix}:{identifier}"
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)

        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start.timestamp())

        # Count current entries
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now.timestamp()): now.timestamp()})

        # Set expiry
        pipe.expire(key, window)

        results = await pipe.execute()
        current_count = results[1]

        is_allowed = current_count < limit
        remaining = max(0, limit - current_count - 1)

        metadata = {
            "limit": limit,
            "remaining": remaining,
            "reset": int((window_start + timedelta(seconds=window)).timestamp()),
        }

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                limit=limit,
            )

        return is_allowed, metadata

    async def wait_for_slot(
        self,
        identifier: str,
        timeout: float = 30.0,
    ) -> bool:
        """Wait until a rate limit slot is available.

        Args:
            identifier: Unique identifier for the rate limit bucket
            timeout: Maximum time to wait in seconds

        Returns:
            True if slot became available, False if timeout
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            is_allowed, metadata = await self.is_allowed(identifier)
            if is_allowed:
                return True

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return False

            # Wait a bit before retrying
            await asyncio.sleep(0.5)


def rate_limit(
    identifier_func: Callable[[dict], str],
    limit: int | None = None,
    window: int | None = None,
):
    """Decorator for rate limiting async functions.

    Args:
        identifier_func: Function to extract identifier from function args
        limit: Maximum requests per window
        window: Window size in seconds

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., Awaitable]):
        async def wrapper(*args, **kwargs):
            # Get rate limiter from context (would be injected via dependency)
            rate_limiter = kwargs.get("_rate_limiter")
            if not rate_limiter:
                return await func(*args, **kwargs)

            identifier = identifier_func(kwargs)
            is_allowed, metadata = await rate_limiter.is_allowed(
                identifier,
                limit=limit,
                window=window,
            )

            if not is_allowed:
                raise Exception(f"Rate limit exceeded. Retry after {metadata['reset']}")

            return await func(*args, **kwargs)

        return wrapper
    return decorator
