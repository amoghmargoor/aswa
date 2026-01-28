"""Prometheus metrics utilities."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


# HTTP Request Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status", "tenant_id"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "tenant_id"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
)


# Document Processing Metrics
documents_processed_total = Counter(
    "documents_processed_total",
    "Total documents processed",
    ["tenant_id", "document_type", "status"],
)

document_processing_duration_seconds = Histogram(
    "document_processing_duration_seconds",
    "Document processing duration in seconds",
    ["tenant_id", "document_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

document_size_bytes = Histogram(
    "document_size_bytes",
    "Document size in bytes",
    ["tenant_id", "document_type"],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],
)

documents_queued = Gauge(
    "documents_queued",
    "Documents currently queued for processing",
    ["tenant_id"],
)


# Insight Metrics
insights_generated_total = Counter(
    "insights_generated_total",
    "Total insights generated",
    ["tenant_id", "insight_type", "severity"],
)

insight_confidence_score = Histogram(
    "insight_confidence_score",
    "Insight confidence score distribution",
    ["tenant_id", "insight_type"],
    buckets=[0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99],
)


# Query Metrics
queries_total = Counter(
    "queries_total",
    "Total queries processed",
    ["tenant_id", "query_type", "status"],
)

query_duration_seconds = Histogram(
    "query_duration_seconds",
    "Query processing duration in seconds",
    ["tenant_id", "query_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

query_tokens_used = Counter(
    "query_tokens_used_total",
    "Total LLM tokens used for queries",
    ["tenant_id", "model"],
)


# Vector Store Metrics
vector_search_total = Counter(
    "vector_search_total",
    "Total vector searches performed",
    ["tenant_id", "status"],
)

vector_search_duration_seconds = Histogram(
    "vector_search_duration_seconds",
    "Vector search duration in seconds",
    ["tenant_id"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

vector_store_documents = Gauge(
    "vector_store_documents",
    "Number of documents in vector store",
    ["tenant_id"],
)


# Database Metrics
db_connections_total = Gauge(
    "db_connections_total",
    "Database connection pool size",
    ["pool"],
)

db_connections_in_use = Gauge(
    "db_connections_in_use",
    "Database connections currently in use",
    ["pool"],
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


# Cache Metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache", "key_type"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache", "key_type"],
)


# Service Info
service_info = Info(
    "aswa_service",
    "ASWA service information",
)


class MetricsRegistry:
    """Registry for Prometheus metrics."""

    def __init__(
        self,
        service_name: str,
        registry: CollectorRegistry | None = None,
    ) -> None:
        """Initialize metrics registry.

        Args:
            service_name: Name of the service
            registry: Optional custom registry
        """
        self.service_name = service_name
        self.registry = registry or CollectorRegistry()
        self._metrics: dict[str, Counter | Histogram | Gauge] = {}

    def counter(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Counter:
        """Create or get a counter metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Counter instance
        """
        full_name = f"{self.service_name}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Counter(
                full_name,
                description,
                labelnames=labels or [],
                registry=self.registry,
            )
        return self._metrics[full_name]  # type: ignore

    def histogram(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """Create or get a histogram metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names
            buckets: Optional histogram buckets

        Returns:
            Histogram instance
        """
        full_name = f"{self.service_name}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Histogram(
                full_name,
                description,
                labelnames=labels or [],
                buckets=buckets or Histogram.DEFAULT_BUCKETS,
                registry=self.registry,
            )
        return self._metrics[full_name]  # type: ignore

    def gauge(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create or get a gauge metric.

        Args:
            name: Metric name
            description: Metric description
            labels: Optional label names

        Returns:
            Gauge instance
        """
        full_name = f"{self.service_name}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Gauge(
                full_name,
                description,
                labelnames=labels or [],
                registry=self.registry,
            )
        return self._metrics[full_name]  # type: ignore


def timed(
    histogram: Histogram,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to time async functions and record to histogram.

    Args:
        histogram: The histogram to record to
        labels: Optional labels

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)

        return wrapper

    return decorator


def track_request_metrics(
    method: str,
    endpoint: str,
    tenant_id: str = "unknown",
) -> Callable:
    """Decorator to track HTTP request metrics.

    Args:
        method: HTTP method
        endpoint: Request endpoint
        tenant_id: Tenant identifier

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                status = "success"
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint,
                    tenant_id=tenant_id,
                ).observe(duration)
                http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status=status,
                    tenant_id=tenant_id,
                ).inc()

        return wrapper
    return decorator


def track_processing_metrics(
    tenant_id: str,
    document_type: str,
) -> Callable:
    """Decorator to track document processing metrics.

    Args:
        tenant_id: Tenant identifier
        document_type: Type of document

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                status = "success"
                return result
            except Exception:
                status = "failed"
                raise
            finally:
                duration = time.time() - start_time
                document_processing_duration_seconds.labels(
                    tenant_id=tenant_id,
                    document_type=document_type,
                ).observe(duration)
                documents_processed_total.labels(
                    tenant_id=tenant_id,
                    document_type=document_type,
                    status=status,
                ).inc()

        return wrapper
    return decorator


class MetricsMiddleware:
    """FastAPI middleware for metrics collection."""

    async def __call__(self, request, call_next):
        method = request.method
        endpoint = request.url.path

        # Extract tenant ID from headers or path
        tenant_id = request.headers.get("X-Tenant-ID", "unknown")

        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
            status = "success" if status_code < 400 else "error"
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.time() - start_time
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
                tenant_id=tenant_id,
            ).observe(duration)

            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status,
                tenant_id=tenant_id,
            ).inc()

        return response
