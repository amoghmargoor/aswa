# Task 7.4.2: Observability - Logging

## Context

You are setting up observability for ASWA at `/infrastructure/kubernetes/`. Prometheus metrics are complete. Now we need structured logging configuration.

## Objective

Create logging configurations that:
1. Implement structured JSON logging
2. Configure log aggregation
3. Set up log correlation with traces
4. Enable log-based alerting
5. Support log retention policies

## Requirements

### 1. Create `/libs/common-python/src/aswa_common/logging.py`
```python
import logging
import sys
import json
import structlog
from datetime import datetime
from typing import Any
import os
import traceback
from contextvars import ContextVar

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")


def add_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add context variables to log entries.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    event_dict["request_id"] = request_id_var.get()
    event_dict["tenant_id"] = tenant_id_var.get()
    event_dict["user_id"] = user_id_var.get()

    trace_id = trace_id_var.get()
    if trace_id:
        event_dict["trace_id"] = trace_id
        event_dict["span_id"] = span_id_var.get()

    return event_dict


def add_service_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add service information to log entries.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    event_dict["service"] = os.environ.get("SERVICE_NAME", "unknown")
    event_dict["environment"] = os.environ.get("ENVIRONMENT", "development")
    event_dict["version"] = os.environ.get("VERSION", "unknown")
    event_dict["host"] = os.environ.get("HOSTNAME", "unknown")

    return event_dict


def format_exception(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Format exception information.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    exc_info = event_dict.pop("exc_info", None)

    if exc_info:
        if isinstance(exc_info, BaseException):
            event_dict["exception"] = {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
                "stacktrace": "".join(traceback.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )),
            }
        elif exc_info is True:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_type:
                event_dict["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "stacktrace": "".join(traceback.format_exception(
                        exc_type, exc_value, exc_tb
                    )),
                }

    return event_dict


class JSONRenderer:
    """Render logs as JSON."""

    def __call__(
        self,
        logger: logging.Logger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> str:
        """Render log entry as JSON.

        Args:
            logger: Logger instance
            method_name: Logging method name
            event_dict: Event dictionary

        Returns:
            JSON string
        """
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        event_dict["level"] = method_name.upper()

        # Ensure message is at top level
        if "event" in event_dict:
            event_dict["message"] = event_dict.pop("event")

        return json.dumps(event_dict, default=str)


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "aswa",
) -> None:
    """Configure structured logging.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format (json, text)
        service_name: Service name for context
    """
    os.environ["SERVICE_NAME"] = service_name

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        add_context,
        add_service_info,
        format_exception,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger.

    Args:
        name: Logger name (optional)

    Returns:
        Configured logger
    """
    return structlog.get_logger(name)


class LoggingMiddleware:
    """FastAPI middleware for request logging."""

    def __init__(self, app):
        """Initialize middleware.

        Args:
            app: FastAPI application
        """
        self.app = app
        self.logger = get_logger("http")

    async def __call__(self, scope, receive, send):
        """Process request with logging.

        Args:
            scope: ASGI scope
            receive: Receive function
            send: Send function
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import uuid
        import time

        # Generate request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        # Extract tenant from headers
        headers = dict(scope.get("headers", []))
        tenant_id = headers.get(b"x-tenant-id", b"").decode()
        user_id = headers.get(b"x-user-id", b"").decode()

        tenant_id_var.set(tenant_id)
        user_id_var.set(user_id)

        # Extract trace context
        traceparent = headers.get(b"traceparent", b"").decode()
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 3:
                trace_id_var.set(parts[1])
                span_id_var.set(parts[2])

        start_time = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.exception(
                "Request failed",
                path=scope.get("path"),
                method=scope.get("method"),
                exc_info=e,
            )
            raise
        finally:
            duration = time.time() - start_time

            self.logger.info(
                "Request completed",
                path=scope.get("path"),
                method=scope.get("method"),
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                client_ip=scope.get("client", ["unknown"])[0],
            )
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/logging/StructuredLogger.java`
```java
package com.aswa.common.logging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Structured JSON logger for ASWA services.
 */
public class StructuredLogger {

    private final Logger logger;
    private final ObjectMapper objectMapper;
    private final String serviceName;

    public StructuredLogger(Class<?> clazz) {
        this.logger = LoggerFactory.getLogger(clazz);
        this.objectMapper = new ObjectMapper();
        this.serviceName = System.getenv().getOrDefault("SERVICE_NAME", "unknown");
    }

    public static StructuredLogger getLogger(Class<?> clazz) {
        return new StructuredLogger(clazz);
    }

    public void info(String message, Object... args) {
        log("INFO", message, null, args);
    }

    public void warn(String message, Object... args) {
        log("WARN", message, null, args);
    }

    public void error(String message, Throwable throwable, Object... args) {
        log("ERROR", message, throwable, args);
    }

    public void debug(String message, Object... args) {
        log("DEBUG", message, null, args);
    }

    private void log(String level, String message, Throwable throwable, Object... args) {
        Map<String, Object> logEntry = new HashMap<>();

        // Base fields
        logEntry.put("timestamp", Instant.now().toString());
        logEntry.put("level", level);
        logEntry.put("message", String.format(message, args));
        logEntry.put("service", serviceName);
        logEntry.put("environment", System.getenv().getOrDefault("ENVIRONMENT", "development"));
        logEntry.put("version", System.getenv().getOrDefault("VERSION", "unknown"));

        // MDC context
        String requestId = MDC.get("requestId");
        if (requestId != null) {
            logEntry.put("request_id", requestId);
        }

        String tenantId = MDC.get("tenantId");
        if (tenantId != null) {
            logEntry.put("tenant_id", tenantId);
        }

        String userId = MDC.get("userId");
        if (userId != null) {
            logEntry.put("user_id", userId);
        }

        String traceId = MDC.get("traceId");
        if (traceId != null) {
            logEntry.put("trace_id", traceId);
            logEntry.put("span_id", MDC.get("spanId"));
        }

        // Exception handling
        if (throwable != null) {
            Map<String, Object> exceptionInfo = new HashMap<>();
            exceptionInfo.put("type", throwable.getClass().getName());
            exceptionInfo.put("message", throwable.getMessage());

            StringBuilder stackTrace = new StringBuilder();
            for (StackTraceElement element : throwable.getStackTrace()) {
                stackTrace.append(element.toString()).append("\n");
            }
            exceptionInfo.put("stacktrace", stackTrace.toString());

            logEntry.put("exception", exceptionInfo);
        }

        try {
            String json = objectMapper.writeValueAsString(logEntry);
            switch (level) {
                case "ERROR" -> logger.error(json);
                case "WARN" -> logger.warn(json);
                case "DEBUG" -> logger.debug(json);
                default -> logger.info(json);
            }
        } catch (JsonProcessingException e) {
            logger.error("Failed to serialize log entry: {}", e.getMessage());
        }
    }

    /**
     * Create a child logger with additional context.
     */
    public ContextBuilder with(String key, Object value) {
        return new ContextBuilder(this).with(key, value);
    }

    public static class ContextBuilder {
        private final StructuredLogger logger;
        private final Map<String, Object> context = new HashMap<>();

        ContextBuilder(StructuredLogger logger) {
            this.logger = logger;
        }

        public ContextBuilder with(String key, Object value) {
            context.put(key, value);
            return this;
        }

        public void info(String message) {
            logWithContext("INFO", message, null);
        }

        public void error(String message, Throwable throwable) {
            logWithContext("ERROR", message, throwable);
        }

        private void logWithContext(String level, String message, Throwable throwable) {
            for (Map.Entry<String, Object> entry : context.entrySet()) {
                MDC.put(entry.getKey(), String.valueOf(entry.getValue()));
            }
            try {
                if (throwable != null) {
                    logger.error(message, throwable);
                } else {
                    logger.info(message);
                }
            } finally {
                for (String key : context.keySet()) {
                    MDC.remove(key);
                }
            }
        }
    }
}
```

### 3. Create `/infrastructure/kubernetes/monitoring/logging/fluentbit-config.yaml`
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: logging
  labels:
    app.kubernetes.io/name: fluent-bit
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Daemon        off
        Parsers_File  parsers.conf
        HTTP_Server   On
        HTTP_Listen   0.0.0.0
        HTTP_Port     2020

    [INPUT]
        Name              tail
        Path              /var/log/containers/aswa-*.log
        Parser            docker
        Tag               kube.*
        Refresh_Interval  5
        Mem_Buf_Limit     50MB
        Skip_Long_Lines   On

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Kube_Tag_Prefix     kube.var.log.containers.
        Merge_Log           On
        Merge_Log_Key       log_processed
        K8S-Logging.Parser  On
        K8S-Logging.Exclude Off

    [FILTER]
        Name    modify
        Match   kube.*
        Add     cluster aswa-prod
        Add     environment production

    [FILTER]
        Name          parser
        Match         kube.*
        Key_Name      log
        Parser        json
        Reserve_Data  True

    [OUTPUT]
        Name            es
        Match           kube.*
        Host            elasticsearch-master
        Port            9200
        Logstash_Format On
        Logstash_Prefix aswa-logs
        Retry_Limit     5
        Replace_Dots    On
        Suppress_Type_Name On

    [OUTPUT]
        Name            loki
        Match           kube.*
        Host            loki-gateway
        Port            80
        Labels          job=aswa, namespace=$kubernetes['namespace_name'], pod=$kubernetes['pod_name'], container=$kubernetes['container_name']
        Label_keys      $level,$service,$tenant_id
        Remove_keys     kubernetes,stream
        Auto_Kubernetes_Labels off

  parsers.conf: |
    [PARSER]
        Name        docker
        Format      json
        Time_Key    time
        Time_Format %Y-%m-%dT%H:%M:%S.%L
        Time_Keep   On

    [PARSER]
        Name        json
        Format      json
        Time_Key    timestamp
        Time_Format %Y-%m-%dT%H:%M:%S.%LZ
        Time_Keep   On
```

### 4. Create `/infrastructure/kubernetes/monitoring/logging/loki-values.yaml`
```yaml
# Loki Helm values for log aggregation
loki:
  auth_enabled: false

  commonConfig:
    replication_factor: 1

  storage:
    bucketNames:
      chunks: aswa-loki-chunks
      ruler: aswa-loki-ruler
      admin: aswa-loki-admin
    type: s3
    s3:
      region: us-east-1
      endpoint: null  # Use AWS default

  schemaConfig:
    configs:
      - from: 2024-01-01
        store: boltdb-shipper
        object_store: s3
        schema: v12
        index:
          prefix: loki_index_
          period: 24h

  limits_config:
    enforce_metric_name: false
    reject_old_samples: true
    reject_old_samples_max_age: 168h  # 7 days
    max_cache_freshness_per_query: 10m
    split_queries_by_interval: 15m

  rulerConfig:
    storage:
      type: local
      local:
        directory: /var/loki/rules
    rule_path: /tmp/rules
    alertmanager_url: http://alertmanager:9093
    ring:
      kvstore:
        store: inmemory
    enable_api: true

write:
  replicas: 2
  persistence:
    size: 10Gi
    storageClass: aswa-ssd

read:
  replicas: 2
  persistence:
    size: 10Gi
    storageClass: aswa-ssd

backend:
  replicas: 1
  persistence:
    size: 10Gi
    storageClass: aswa-ssd

gateway:
  enabled: true
  replicas: 2

monitoring:
  serviceMonitor:
    enabled: true
  selfMonitoring:
    enabled: false
  lokiCanary:
    enabled: false
```

### 5. Create `/infrastructure/kubernetes/monitoring/logging/log-alerts.yaml`
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: aswa-log-alerts
  namespace: monitoring
  labels:
    app.kubernetes.io/name: aswa
spec:
  groups:
    - name: aswa.log.alerts
      rules:
        - alert: ASWAHighErrorLogRate
          expr: |
            sum(rate({job="aswa", level="ERROR"}[5m])) > 10
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High error log rate detected"
            description: "More than 10 error logs per second in the last 5 minutes"

        - alert: ASWAAuthenticationFailures
          expr: |
            sum(rate({job="aswa", message=~".*authentication failed.*"}[5m])) > 5
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High authentication failure rate"
            description: "More than 5 authentication failures per second"

        - alert: ASWADatabaseConnectionErrors
          expr: |
            sum(rate({job="aswa", message=~".*database connection.*error.*"}[5m])) > 0
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "Database connection errors detected"
            description: "Database connection errors occurring"

        - alert: ASWAExternalAPIErrors
          expr: |
            sum(rate({job="aswa", message=~".*(openai|anthropic).*error.*"}[5m])) > 1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "External API errors detected"
            description: "Errors communicating with external LLM APIs"
```

## Verification

1. Configure logging in services: Import and use structured logging
2. Deploy Fluent Bit: `helm install fluent-bit fluent/fluent-bit -f fluentbit-values.yaml`
3. Deploy Loki: `helm install loki grafana/loki -f loki-values.yaml`
4. Verify logs in Grafana: Query Loki datasource
5. Test log correlation with traces
