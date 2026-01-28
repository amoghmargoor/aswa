import time
from typing import Callable
from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from aswa_query.config import get_settings

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid4())
        start_time = time.time()

        # Add request ID to state
        request.state.request_id = request_id

        # Log request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        # Log response
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Request completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = str(duration_ms)

        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract and validate tenant context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            try:
                request.state.tenant_id = UUID(tenant_id)
            except ValueError:
                pass

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""

    def __init__(self, app):
        super().__init__(app)
        self._request_counts: dict[str, list[float]] = {}
        self.settings = get_settings()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/live"]:
            return await call_next(request)

        # Get client identifier
        client_id = request.headers.get("X-Tenant-ID", request.client.host if request.client else "unknown")

        # Check rate limit
        now = time.time()
        window_start = now - self.settings.rate_limit_window_seconds

        if client_id not in self._request_counts:
            self._request_counts[client_id] = []

        # Clean old requests
        self._request_counts[client_id] = [
            t for t in self._request_counts[client_id] if t > window_start
        ]

        if len(self._request_counts[client_id]) >= self.settings.rate_limit_requests:
            return Response(
                content='{"error": "rate_limit_exceeded", "message": "Too many requests"}',
                status_code=429,
                media_type="application/json",
            )

        self._request_counts[client_id].append(now)

        return await call_next(request)
