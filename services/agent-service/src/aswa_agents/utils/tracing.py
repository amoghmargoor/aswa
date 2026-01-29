"""OpenTelemetry tracing configuration."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from aswa_agents.config import Settings


def setup_tracing(settings: Settings) -> None:
    """Configure OpenTelemetry tracing."""
    resource = Resource.create({
        "service.name": settings.service_name,
        "service.version": "0.1.0",
        "deployment.environment": settings.environment,
    })

    provider = TracerProvider(resource=resource)

    if settings.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def instrument_app(app) -> None:
    """Instrument FastAPI application with tracing."""
    FastAPIInstrumentor.instrument_app(app)
