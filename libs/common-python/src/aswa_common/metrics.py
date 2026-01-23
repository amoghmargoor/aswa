"""Prometheus metrics utilities."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

T = TypeVar("T")


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
