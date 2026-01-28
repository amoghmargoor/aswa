import os
from typing import Optional, Callable, Any
from functools import wraps
from contextlib import asynccontextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased

import structlog

logger = structlog.get_logger()


def configure_tracing(
    service_name: str,
    service_version: str = "1.0.0",
    otlp_endpoint: str | None = None,
    sampling_rate: float = 1.0,
) -> trace.Tracer:
    """Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        service_version: Service version
        otlp_endpoint: OTLP collector endpoint
        sampling_rate: Trace sampling rate (0.0-1.0)

    Returns:
        Configured tracer
    """
    # Create resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
        "host.name": os.environ.get("HOSTNAME", "unknown"),
    })

    # Configure sampler
    sampler = ParentBased(
        root=TraceIdRatioBased(sampling_rate)
    )

    # Create tracer provider
    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    # Configure exporter
    endpoint = otlp_endpoint or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4317"
    )

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Configure propagators
    set_global_textmap(TraceContextTextMapPropagator())

    logger.info(
        "Tracing configured",
        service=service_name,
        endpoint=endpoint,
        sampling_rate=sampling_rate,
    )

    return trace.get_tracer(service_name)


def instrument_fastapi(app) -> None:
    """Instrument FastAPI application.

    Args:
        app: FastAPI application instance
    """
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,health/ready,metrics",
    )


def instrument_httpx() -> None:
    """Instrument HTTPX client."""
    HTTPXClientInstrumentor().instrument()


def instrument_sqlalchemy(engine) -> None:
    """Instrument SQLAlchemy engine.

    Args:
        engine: SQLAlchemy engine
    """
    SQLAlchemyInstrumentor().instrument(engine=engine)


def instrument_redis(client) -> None:
    """Instrument Redis client.

    Args:
        client: Redis client
    """
    RedisInstrumentor().instrument()


def get_tracer(name: str | None = None) -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name (optional)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name or __name__)


def trace_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to trace a function or method.

    Args:
        name: Span name
        attributes: Span attributes

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        tracer = get_tracer()

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(
                        trace.StatusCode.ERROR,
                        str(e),
                    ))
                    span.record_exception(e)
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(
                        trace.StatusCode.ERROR,
                        str(e),
                    ))
                    span.record_exception(e)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@asynccontextmanager
async def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
):
    """Context manager for creating a trace span.

    Args:
        name: Span name
        attributes: Span attributes

    Yields:
        Current span
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def add_span_attributes(**kwargs) -> None:
    """Add attributes to the current span.

    Args:
        **kwargs: Attribute key-value pairs
    """
    span = trace.get_current_span()
    for key, value in kwargs.items():
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span.

    Args:
        name: Event name
        attributes: Event attributes
    """
    span = trace.get_current_span()
    span.add_event(name, attributes=attributes)


def get_trace_context() -> dict[str, str]:
    """Get current trace context for propagation.

    Returns:
        Trace context headers
    """
    from opentelemetry.propagate import inject

    carrier = {}
    inject(carrier)
    return carrier


def set_trace_context(headers: dict[str, str]) -> None:
    """Set trace context from headers.

    Args:
        headers: Incoming trace headers
    """
    from opentelemetry.propagate import extract

    context = extract(headers)
    # Context is automatically used for child spans


import asyncio  # Import at the end to avoid circular issues
