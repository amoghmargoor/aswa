# Task 7.4.3: Observability - Distributed Tracing

## Context

You are setting up observability for ASWA at `/infrastructure/kubernetes/`. Logging is complete. Now we need distributed tracing with OpenTelemetry.

## Objective

Create distributed tracing configurations that:
1. Implement OpenTelemetry instrumentation
2. Configure trace propagation
3. Set up Jaeger for trace visualization
4. Enable trace sampling strategies
5. Support trace correlation with logs

## Requirements

### 1. Create `/libs/common-python/src/aswa_common/tracing.py`
```python
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/tracing/TracingConfig.java`
```java
package com.aswa.common.tracing;

import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.Scope;
import io.opentelemetry.context.propagation.TextMapGetter;
import io.opentelemetry.context.propagation.TextMapPropagator;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.samplers.Sampler;
import io.opentelemetry.semconv.resource.attributes.ResourceAttributes;

import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/**
 * OpenTelemetry tracing configuration for Java services.
 */
public class TracingConfig {

    private static Tracer tracer;
    private static TextMapPropagator propagator;

    /**
     * Initialize OpenTelemetry tracing.
     */
    public static void initialize(String serviceName, String serviceVersion) {
        String otlpEndpoint = System.getenv().getOrDefault(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4317"
        );

        double samplingRate = Double.parseDouble(
            System.getenv().getOrDefault("OTEL_TRACES_SAMPLER_ARG", "1.0")
        );

        Resource resource = Resource.getDefault().merge(
            Resource.builder()
                .put(ResourceAttributes.SERVICE_NAME, serviceName)
                .put(ResourceAttributes.SERVICE_VERSION, serviceVersion)
                .put("deployment.environment",
                    System.getenv().getOrDefault("ENVIRONMENT", "development"))
                .build()
        );

        OtlpGrpcSpanExporter exporter = OtlpGrpcSpanExporter.builder()
            .setEndpoint(otlpEndpoint)
            .setTimeout(10, TimeUnit.SECONDS)
            .build();

        SdkTracerProvider tracerProvider = SdkTracerProvider.builder()
            .setResource(resource)
            .setSampler(Sampler.parentBased(Sampler.traceIdRatioBased(samplingRate)))
            .addSpanProcessor(BatchSpanProcessor.builder(exporter).build())
            .build();

        OpenTelemetrySdk openTelemetry = OpenTelemetrySdk.builder()
            .setTracerProvider(tracerProvider)
            .buildAndRegisterGlobal();

        tracer = openTelemetry.getTracer(serviceName);
        propagator = openTelemetry.getPropagators().getTextMapPropagator();
    }

    /**
     * Get the tracer instance.
     */
    public static Tracer getTracer() {
        if (tracer == null) {
            return GlobalOpenTelemetry.getTracer("aswa");
        }
        return tracer;
    }

    /**
     * Create a new span for an operation.
     */
    public static <T> T traceOperation(String name, Map<String, String> attributes, Supplier<T> operation) {
        Span span = getTracer().spanBuilder(name)
            .setSpanKind(SpanKind.INTERNAL)
            .startSpan();

        if (attributes != null) {
            attributes.forEach(span::setAttribute);
        }

        try (Scope scope = span.makeCurrent()) {
            T result = operation.get();
            span.setStatus(StatusCode.OK);
            return result;
        } catch (Exception e) {
            span.setStatus(StatusCode.ERROR, e.getMessage());
            span.recordException(e);
            throw e;
        } finally {
            span.end();
        }
    }

    /**
     * Create a new span for an async operation.
     */
    public static Span startSpan(String name, SpanKind kind) {
        return getTracer().spanBuilder(name)
            .setSpanKind(kind)
            .startSpan();
    }

    /**
     * Extract context from headers.
     */
    public static Context extractContext(Map<String, String> headers) {
        return propagator.extract(Context.current(), headers, new TextMapGetter<>() {
            @Override
            public Iterable<String> keys(Map<String, String> carrier) {
                return carrier.keySet();
            }

            @Override
            public String get(Map<String, String> carrier, String key) {
                return carrier.get(key);
            }
        });
    }

    /**
     * Inject context into headers.
     */
    public static void injectContext(Map<String, String> headers) {
        propagator.inject(Context.current(), headers, Map::put);
    }

    /**
     * Add attributes to the current span.
     */
    public static void addSpanAttributes(Map<String, String> attributes) {
        Span span = Span.current();
        attributes.forEach(span::setAttribute);
    }

    /**
     * Add an event to the current span.
     */
    public static void addSpanEvent(String name, Map<String, String> attributes) {
        Span span = Span.current();
        if (attributes != null) {
            span.addEvent(name, io.opentelemetry.api.common.Attributes.builder()
                .put("event.name", name)
                .build());
        } else {
            span.addEvent(name);
        }
    }
}
```

### 3. Create `/infrastructure/kubernetes/monitoring/tracing/jaeger.yaml`
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: observability
  labels:
    app.kubernetes.io/name: observability
---
# Jaeger Operator
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: aswa-jaeger
  namespace: observability
spec:
  strategy: production

  collector:
    replicas: 2
    maxReplicas: 5
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
      limits:
        cpu: 1000m
        memory: 1Gi
    options:
      collector:
        zipkin:
          host-port: ":9411"

  query:
    replicas: 2
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
    options:
      query:
        base-path: /jaeger

  agent:
    strategy: DaemonSet

  storage:
    type: elasticsearch
    options:
      es:
        server-urls: http://elasticsearch-master:9200
        index-prefix: jaeger
        num-shards: 3
        num-replicas: 1

    esIndexCleaner:
      enabled: true
      numberOfDays: 7
      schedule: "55 23 * * *"

  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: nginx
      cert-manager.io/cluster-issuer: letsencrypt-prod
    hosts:
      - jaeger.aswa.io
    tls:
      - secretName: jaeger-tls
        hosts:
          - jaeger.aswa.io

---
# OpenTelemetry Collector
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: aswa-otel-collector
  namespace: observability
spec:
  mode: deployment
  replicas: 2

  config: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318

      zipkin:
        endpoint: 0.0.0.0:9411

    processors:
      batch:
        timeout: 5s
        send_batch_size: 1000

      memory_limiter:
        check_interval: 1s
        limit_mib: 1000
        spike_limit_mib: 200

      attributes:
        actions:
          - key: environment
            value: production
            action: upsert

      tail_sampling:
        decision_wait: 10s
        policies:
          - name: errors
            type: status_code
            status_code:
              status_codes: [ERROR]
          - name: slow-traces
            type: latency
            latency:
              threshold_ms: 5000
          - name: probabilistic
            type: probabilistic
            probabilistic:
              sampling_percentage: 10

    exporters:
      jaeger:
        endpoint: aswa-jaeger-collector:14250
        tls:
          insecure: true

      prometheus:
        endpoint: 0.0.0.0:8889

    service:
      pipelines:
        traces:
          receivers: [otlp, zipkin]
          processors: [memory_limiter, batch, attributes, tail_sampling]
          exporters: [jaeger]

        metrics:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [prometheus]

  resources:
    requests:
      cpu: 200m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 1Gi
```

### 4. Create `/infrastructure/kubernetes/monitoring/tracing/servicemonitor.yaml`
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: otel-collector
  namespace: monitoring
  labels:
    app.kubernetes.io/name: otel-collector
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa-otel-collector
  namespaceSelector:
    matchNames:
      - observability
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: jaeger
  namespace: monitoring
  labels:
    app.kubernetes.io/name: jaeger
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa-jaeger
  namespaceSelector:
    matchNames:
      - observability
  endpoints:
    - port: admin-http
      interval: 15s
      path: /metrics
```

## Verification

1. Deploy Jaeger: `kubectl apply -f infrastructure/kubernetes/monitoring/tracing/`
2. Deploy OpenTelemetry Collector
3. Instrument services with tracing
4. Generate test traffic
5. View traces in Jaeger UI
6. Verify trace-log correlation
