# Task 7.4.1: Observability - Prometheus Metrics

## Context

You are setting up observability for ASWA at `/infrastructure/kubernetes/`. This task focuses on Prometheus metrics collection and configuration.

## Objective

Create Prometheus configurations that:
1. Define custom metrics for each service
2. Configure ServiceMonitors for scraping
3. Set up alerting rules
4. Enable metric aggregation
5. Support multi-tenant metrics

## Requirements

### 1. Create `/infrastructure/kubernetes/monitoring/prometheus/servicemonitor.yaml`
```yaml
# API Gateway ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aswa-api-gateway
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: api-gateway
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa
      app.kubernetes.io/component: api-gateway
  namespaceSelector:
    matchNames:
      - aswa-prod
      - aswa-staging
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
      relabelings:
        - sourceLabels: [__meta_kubernetes_namespace]
          targetLabel: namespace
        - sourceLabels: [__meta_kubernetes_pod_name]
          targetLabel: pod
        - sourceLabels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]
          targetLabel: component
---
# Ingestion Service ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aswa-ingestion
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: ingestion
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa
      app.kubernetes.io/component: ingestion
  namespaceSelector:
    matchNames:
      - aswa-prod
      - aswa-staging
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
---
# Query Service ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aswa-query
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: query
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa
      app.kubernetes.io/component: query
  namespaceSelector:
    matchNames:
      - aswa-prod
      - aswa-staging
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
---
# Insight Service ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aswa-insight
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
    app.kubernetes.io/component: insight
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: aswa
      app.kubernetes.io/component: insight
  namespaceSelector:
    matchNames:
      - aswa-prod
      - aswa-staging
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
```

### 2. Create `/libs/common-python/src/aswa_common/metrics.py`
```python
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable, Any
import structlog

logger = structlog.get_logger()


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
            except Exception as e:
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
            status_code = 500
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
```

### 3. Create `/infrastructure/kubernetes/monitoring/prometheus/alerting-rules.yaml`
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: aswa-alerts
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
    prometheus: kube-prometheus
spec:
  groups:
    - name: aswa.availability
      rules:
        - alert: ASWAServiceDown
          expr: up{job=~"aswa-.*"} == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "ASWA service {{ $labels.job }} is down"
            description: "{{ $labels.job }} has been down for more than 5 minutes."

        - alert: ASWAHighErrorRate
          expr: |
            sum(rate(http_requests_total{status="error", job=~"aswa-.*"}[5m])) by (job)
            /
            sum(rate(http_requests_total{job=~"aswa-.*"}[5m])) by (job)
            > 0.05
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High error rate on {{ $labels.job }}"
            description: "Error rate is {{ $value | humanizePercentage }} (> 5%)"

        - alert: ASWACriticalErrorRate
          expr: |
            sum(rate(http_requests_total{status="error", job=~"aswa-.*"}[5m])) by (job)
            /
            sum(rate(http_requests_total{job=~"aswa-.*"}[5m])) by (job)
            > 0.2
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "Critical error rate on {{ $labels.job }}"
            description: "Error rate is {{ $value | humanizePercentage }} (> 20%)"

    - name: aswa.latency
      rules:
        - alert: ASWAHighLatency
          expr: |
            histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job=~"aswa-.*"}[5m])) by (le, job))
            > 2
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High latency on {{ $labels.job }}"
            description: "P95 latency is {{ $value | humanizeDuration }}"

        - alert: ASWAQueryTimeout
          expr: |
            histogram_quantile(0.99, sum(rate(query_duration_seconds_bucket[5m])) by (le))
            > 30
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Query processing is timing out"
            description: "P99 query duration is {{ $value | humanizeDuration }}"

    - name: aswa.resources
      rules:
        - alert: ASWAHighCPU
          expr: |
            sum(rate(container_cpu_usage_seconds_total{namespace=~"aswa-.*", container!=""}[5m])) by (pod)
            /
            sum(kube_pod_container_resource_limits{namespace=~"aswa-.*", resource="cpu"}) by (pod)
            > 0.9
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High CPU usage on {{ $labels.pod }}"
            description: "CPU usage is {{ $value | humanizePercentage }}"

        - alert: ASWAHighMemory
          expr: |
            sum(container_memory_working_set_bytes{namespace=~"aswa-.*", container!=""}) by (pod)
            /
            sum(kube_pod_container_resource_limits{namespace=~"aswa-.*", resource="memory"}) by (pod)
            > 0.9
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High memory usage on {{ $labels.pod }}"
            description: "Memory usage is {{ $value | humanizePercentage }}"

        - alert: ASWAPodRestarting
          expr: |
            increase(kube_pod_container_status_restarts_total{namespace=~"aswa-.*"}[1h]) > 3
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} is restarting frequently"
            description: "{{ $value }} restarts in the last hour"

    - name: aswa.business
      rules:
        - alert: ASWADocumentProcessingBacklog
          expr: documents_queued > 100
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "Document processing backlog for tenant {{ $labels.tenant_id }}"
            description: "{{ $value }} documents queued"

        - alert: ASWALowInsightConfidence
          expr: |
            histogram_quantile(0.5, sum(rate(insight_confidence_score_bucket[1h])) by (le, tenant_id))
            < 0.7
          for: 30m
          labels:
            severity: warning
          annotations:
            summary: "Low insight confidence for tenant {{ $labels.tenant_id }}"
            description: "Median confidence is {{ $value }}"

        - alert: ASWAHighTokenUsage
          expr: |
            sum(increase(query_tokens_used_total[1h])) by (tenant_id) > 100000
          labels:
            severity: warning
          annotations:
            summary: "High token usage for tenant {{ $labels.tenant_id }}"
            description: "{{ $value | humanize }} tokens used in the last hour"

    - name: aswa.database
      rules:
        - alert: ASWADatabaseConnectionExhausted
          expr: |
            db_connections_in_use / db_connections_total > 0.9
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Database connection pool nearly exhausted"
            description: "{{ $value | humanizePercentage }} of connections in use"

        - alert: ASWASlowDatabaseQueries
          expr: |
            histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (le, operation))
            > 1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Slow database queries for {{ $labels.operation }}"
            description: "P95 query time is {{ $value | humanizeDuration }}"
```

### 4. Create `/infrastructure/kubernetes/monitoring/prometheus/recording-rules.yaml`
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: aswa-recording-rules
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
spec:
  groups:
    - name: aswa.aggregations
      interval: 30s
      rules:
        # Request rate by service
        - record: aswa:http_requests_rate5m
          expr: sum(rate(http_requests_total[5m])) by (job, namespace)

        # Error rate by service
        - record: aswa:http_error_rate5m
          expr: |
            sum(rate(http_requests_total{status="error"}[5m])) by (job, namespace)
            /
            sum(rate(http_requests_total[5m])) by (job, namespace)

        # P50 latency
        - record: aswa:http_latency_p50
          expr: histogram_quantile(0.5, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job))

        # P95 latency
        - record: aswa:http_latency_p95
          expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job))

        # P99 latency
        - record: aswa:http_latency_p99
          expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, job))

        # Documents processed per hour
        - record: aswa:documents_processed_1h
          expr: sum(increase(documents_processed_total[1h])) by (tenant_id)

        # Insights generated per hour
        - record: aswa:insights_generated_1h
          expr: sum(increase(insights_generated_total[1h])) by (tenant_id, insight_type)

        # Queries per hour
        - record: aswa:queries_1h
          expr: sum(increase(queries_total[1h])) by (tenant_id)

        # Token usage per hour
        - record: aswa:tokens_used_1h
          expr: sum(increase(query_tokens_used_total[1h])) by (tenant_id, model)

        # Cache hit rate
        - record: aswa:cache_hit_rate
          expr: |
            sum(rate(cache_hits_total[5m])) by (cache)
            /
            (sum(rate(cache_hits_total[5m])) by (cache) + sum(rate(cache_misses_total[5m])) by (cache))
```

## Verification

1. Apply ServiceMonitors: `kubectl apply -f infrastructure/kubernetes/monitoring/prometheus/`
2. Verify targets in Prometheus: Check Prometheus UI targets page
3. Test alerting rules: Trigger test alerts
4. Verify metrics are being collected
5. Check recording rules are generating metrics
