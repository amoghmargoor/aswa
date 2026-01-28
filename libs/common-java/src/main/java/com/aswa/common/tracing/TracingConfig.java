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
