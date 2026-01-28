# Task 8.3.1: Audit & Compliance - Audit Logging

## Context

You are implementing audit and compliance for ASWA. Data security is complete. Now we need comprehensive audit logging.

## Objective

Create audit logging implementation that:
1. Logs all security-relevant events
2. Captures user actions and data access
3. Implements tamper-evident logging
4. Supports searchable audit trails
5. Enables compliance reporting

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/audit/AuditEvent.java`
```java
package com.aswa.common.audit;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * Audit event record.
 */
public record AuditEvent(
    String id,
    Instant timestamp,
    String tenantId,
    String userId,
    String userEmail,
    String userRole,
    AuditAction action,
    AuditCategory category,
    String resourceType,
    String resourceId,
    AuditResult result,
    String ipAddress,
    String userAgent,
    String sessionId,
    String traceId,
    Map<String, Object> metadata,
    Map<String, Object> before,
    Map<String, Object> after,
    String errorMessage
) {

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String id = UUID.randomUUID().toString();
        private Instant timestamp = Instant.now();
        private String tenantId;
        private String userId;
        private String userEmail;
        private String userRole;
        private AuditAction action;
        private AuditCategory category;
        private String resourceType;
        private String resourceId;
        private AuditResult result = AuditResult.SUCCESS;
        private String ipAddress;
        private String userAgent;
        private String sessionId;
        private String traceId;
        private Map<String, Object> metadata = Map.of();
        private Map<String, Object> before;
        private Map<String, Object> after;
        private String errorMessage;

        public Builder id(String id) { this.id = id; return this; }
        public Builder timestamp(Instant timestamp) { this.timestamp = timestamp; return this; }
        public Builder tenantId(String tenantId) { this.tenantId = tenantId; return this; }
        public Builder userId(String userId) { this.userId = userId; return this; }
        public Builder userEmail(String userEmail) { this.userEmail = userEmail; return this; }
        public Builder userRole(String userRole) { this.userRole = userRole; return this; }
        public Builder action(AuditAction action) { this.action = action; return this; }
        public Builder category(AuditCategory category) { this.category = category; return this; }
        public Builder resourceType(String resourceType) { this.resourceType = resourceType; return this; }
        public Builder resourceId(String resourceId) { this.resourceId = resourceId; return this; }
        public Builder result(AuditResult result) { this.result = result; return this; }
        public Builder ipAddress(String ipAddress) { this.ipAddress = ipAddress; return this; }
        public Builder userAgent(String userAgent) { this.userAgent = userAgent; return this; }
        public Builder sessionId(String sessionId) { this.sessionId = sessionId; return this; }
        public Builder traceId(String traceId) { this.traceId = traceId; return this; }
        public Builder metadata(Map<String, Object> metadata) { this.metadata = metadata; return this; }
        public Builder before(Map<String, Object> before) { this.before = before; return this; }
        public Builder after(Map<String, Object> after) { this.after = after; return this; }
        public Builder errorMessage(String errorMessage) { this.errorMessage = errorMessage; return this; }

        public AuditEvent build() {
            return new AuditEvent(id, timestamp, tenantId, userId, userEmail, userRole,
                action, category, resourceType, resourceId, result, ipAddress, userAgent,
                sessionId, traceId, metadata, before, after, errorMessage);
        }
    }
}
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/audit/AuditAction.java`
```java
package com.aswa.common.audit;

/**
 * Audit action types.
 */
public enum AuditAction {
    // Authentication
    LOGIN("login", "User login"),
    LOGOUT("logout", "User logout"),
    LOGIN_FAILED("login_failed", "Failed login attempt"),
    PASSWORD_CHANGE("password_change", "Password changed"),
    PASSWORD_RESET("password_reset", "Password reset requested"),
    MFA_ENABLED("mfa_enabled", "MFA enabled"),
    MFA_DISABLED("mfa_disabled", "MFA disabled"),
    SESSION_REVOKED("session_revoked", "Session revoked"),

    // Resource operations
    CREATE("create", "Resource created"),
    READ("read", "Resource accessed"),
    UPDATE("update", "Resource updated"),
    DELETE("delete", "Resource deleted"),
    EXPORT("export", "Data exported"),
    IMPORT("import", "Data imported"),

    // Document operations
    DOCUMENT_UPLOAD("document_upload", "Document uploaded"),
    DOCUMENT_DOWNLOAD("document_download", "Document downloaded"),
    DOCUMENT_PROCESS("document_process", "Document processed"),
    DOCUMENT_DELETE("document_delete", "Document deleted"),

    // Query operations
    QUERY_EXECUTE("query_execute", "Query executed"),
    INSIGHT_GENERATE("insight_generate", "Insight generated"),

    // Admin operations
    USER_CREATE("user_create", "User created"),
    USER_UPDATE("user_update", "User updated"),
    USER_DELETE("user_delete", "User deleted"),
    ROLE_CHANGE("role_change", "User role changed"),
    PERMISSION_GRANT("permission_grant", "Permission granted"),
    PERMISSION_REVOKE("permission_revoke", "Permission revoked"),

    // System operations
    CONFIG_CHANGE("config_change", "Configuration changed"),
    API_KEY_CREATE("api_key_create", "API key created"),
    API_KEY_REVOKE("api_key_revoke", "API key revoked"),
    WEBHOOK_CREATE("webhook_create", "Webhook created"),
    INTEGRATION_ENABLE("integration_enable", "Integration enabled");

    private final String code;
    private final String description;

    AuditAction(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/audit/AuditCategory.java`
```java
package com.aswa.common.audit;

/**
 * Audit event categories.
 */
public enum AuditCategory {
    AUTHENTICATION("authentication", "Authentication events"),
    AUTHORIZATION("authorization", "Authorization events"),
    DATA_ACCESS("data_access", "Data access events"),
    DATA_MODIFICATION("data_modification", "Data modification events"),
    ADMIN("admin", "Administrative events"),
    SECURITY("security", "Security events"),
    SYSTEM("system", "System events");

    private final String code;
    private final String description;

    AuditCategory(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/audit/AuditService.java`
```java
package com.aswa.common.audit;

import com.aswa.common.auth.UserPrincipal;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.opentelemetry.api.trace.Span;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Audit logging service.
 */
@Service
public class AuditService {

    private static final Logger logger = LoggerFactory.getLogger(AuditService.class);
    private static final String AUDIT_TOPIC = "aswa.audit.events";

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final AuditRepository auditRepository;
    private final ObjectMapper objectMapper;

    public AuditService(
            KafkaTemplate<String, String> kafkaTemplate,
            AuditRepository auditRepository,
            ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.auditRepository = auditRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Log an audit event.
     */
    public void log(AuditEvent event) {
        try {
            // Add integrity hash
            String eventJson = objectMapper.writeValueAsString(event);
            String hash = computeHash(eventJson);

            AuditEventWithHash eventWithHash = new AuditEventWithHash(event, hash);
            String finalJson = objectMapper.writeValueAsString(eventWithHash);

            // Send to Kafka for async processing
            kafkaTemplate.send(AUDIT_TOPIC, event.tenantId(), finalJson);

            // Also log to structured logger
            logger.info("AUDIT: {} {} {} on {} {}",
                event.action().getCode(),
                event.result(),
                event.userId(),
                event.resourceType(),
                event.resourceId());

        } catch (Exception e) {
            logger.error("Failed to log audit event", e);
        }
    }

    /**
     * Log with current user context.
     */
    public void log(
            AuditAction action,
            AuditCategory category,
            String resourceType,
            String resourceId,
            AuditResult result,
            Map<String, Object> metadata) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        AuditEvent event = AuditEvent.builder()
            .action(action)
            .category(category)
            .resourceType(resourceType)
            .resourceId(resourceId)
            .result(result)
            .tenantId(user != null ? user.getTenantId() : null)
            .userId(user != null ? user.getId() : null)
            .userEmail(user != null ? user.getEmail() : null)
            .userRole(user != null ? user.getRole() : null)
            .ipAddress(request != null ? getClientIp(request) : null)
            .userAgent(request != null ? request.getHeader("User-Agent") : null)
            .sessionId(request != null ? request.getHeader("X-Session-Id") : null)
            .traceId(Span.current().getSpanContext().getTraceId())
            .metadata(metadata)
            .build();

        log(event);
    }

    /**
     * Log data modification with before/after state.
     */
    public void logModification(
            AuditAction action,
            String resourceType,
            String resourceId,
            Object before,
            Object after) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        try {
            AuditEvent event = AuditEvent.builder()
                .action(action)
                .category(AuditCategory.DATA_MODIFICATION)
                .resourceType(resourceType)
                .resourceId(resourceId)
                .result(AuditResult.SUCCESS)
                .tenantId(user != null ? user.getTenantId() : null)
                .userId(user != null ? user.getId() : null)
                .userEmail(user != null ? user.getEmail() : null)
                .userRole(user != null ? user.getRole() : null)
                .ipAddress(request != null ? getClientIp(request) : null)
                .userAgent(request != null ? request.getHeader("User-Agent") : null)
                .traceId(Span.current().getSpanContext().getTraceId())
                .before(objectMapper.convertValue(before, Map.class))
                .after(objectMapper.convertValue(after, Map.class))
                .build();

            log(event);
        } catch (Exception e) {
            logger.error("Failed to log modification audit", e);
        }
    }

    /**
     * Log failed operation.
     */
    public void logFailure(
            AuditAction action,
            AuditCategory category,
            String resourceType,
            String resourceId,
            String errorMessage) {

        UserPrincipal user = getCurrentUser();
        HttpServletRequest request = getCurrentRequest();

        AuditEvent event = AuditEvent.builder()
            .action(action)
            .category(category)
            .resourceType(resourceType)
            .resourceId(resourceId)
            .result(AuditResult.FAILURE)
            .errorMessage(errorMessage)
            .tenantId(user != null ? user.getTenantId() : null)
            .userId(user != null ? user.getId() : null)
            .userEmail(user != null ? user.getEmail() : null)
            .userRole(user != null ? user.getRole() : null)
            .ipAddress(request != null ? getClientIp(request) : null)
            .userAgent(request != null ? request.getHeader("User-Agent") : null)
            .traceId(Span.current().getSpanContext().getTraceId())
            .build();

        log(event);
    }

    /**
     * Search audit logs.
     */
    public CompletableFuture<AuditSearchResult> search(AuditSearchCriteria criteria) {
        return auditRepository.search(criteria);
    }

    private String computeHash(String data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data.getBytes());
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            return null;
        }
    }

    private UserPrincipal getCurrentUser() {
        // Get from SecurityContext
        return null; // Implementation depends on security setup
    }

    private HttpServletRequest getCurrentRequest() {
        try {
            ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.currentRequestAttributes();
            return attrs.getRequest();
        } catch (Exception e) {
            return null;
        }
    }

    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    public record AuditEventWithHash(AuditEvent event, String hash) {}
}
```

### 5. Create `/libs/common-python/src/aswa_common/audit.py`
```python
"""Audit logging for Python services."""

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from opentelemetry import trace

logger = structlog.get_logger("audit")


class AuditAction(Enum):
    """Audit action types."""
    # Authentication
    LOGIN = ("login", "User login")
    LOGOUT = ("logout", "User logout")
    LOGIN_FAILED = ("login_failed", "Failed login attempt")

    # Resource operations
    CREATE = ("create", "Resource created")
    READ = ("read", "Resource accessed")
    UPDATE = ("update", "Resource updated")
    DELETE = ("delete", "Resource deleted")

    # Document operations
    DOCUMENT_UPLOAD = ("document_upload", "Document uploaded")
    DOCUMENT_DOWNLOAD = ("document_download", "Document downloaded")
    DOCUMENT_PROCESS = ("document_process", "Document processed")

    # Query operations
    QUERY_EXECUTE = ("query_execute", "Query executed")
    INSIGHT_GENERATE = ("insight_generate", "Insight generated")

    def __init__(self, code: str, description: str):
        self.code = code
        self.description = description


class AuditCategory(Enum):
    """Audit event categories."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    ADMIN = "admin"
    SECURITY = "security"
    SYSTEM = "system"


class AuditResult(Enum):
    """Audit result types."""
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


@dataclass
class AuditEvent:
    """Audit event record."""
    action: AuditAction
    category: AuditCategory
    result: AuditResult = AuditResult.SUCCESS
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    before: Optional[dict] = None
    after: Optional[dict] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["action"] = self.action.code
        data["category"] = self.category.value
        data["result"] = self.result.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """Audit logging service."""

    def __init__(self, kafka_producer=None, repository=None):
        self.kafka_producer = kafka_producer
        self.repository = repository
        self.topic = "aswa.audit.events"

    async def log(self, event: AuditEvent) -> None:
        """Log an audit event."""
        try:
            # Add trace ID if not set
            if not event.trace_id:
                span = trace.get_current_span()
                if span:
                    event.trace_id = span.get_span_context().trace_id

            # Compute integrity hash
            event_dict = event.to_dict()
            event_json = json.dumps(event_dict, sort_keys=True, default=str)
            hash_value = hashlib.sha256(event_json.encode()).hexdigest()

            event_with_hash = {
                "event": event_dict,
                "hash": hash_value,
            }

            # Send to Kafka
            if self.kafka_producer:
                await self.kafka_producer.send(
                    self.topic,
                    key=event.tenant_id,
                    value=json.dumps(event_with_hash),
                )

            # Also log to structured logger
            logger.info(
                "audit_event",
                action=event.action.code,
                result=event.result.value,
                user_id=event.user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
            )

        except Exception as e:
            logger.error("Failed to log audit event", error=str(e))

    async def log_action(
        self,
        action: AuditAction,
        category: AuditCategory,
        resource_type: str,
        resource_id: str,
        result: AuditResult = AuditResult.SUCCESS,
        metadata: Optional[dict] = None,
        user_context: Optional[dict] = None,
        request_context: Optional[dict] = None,
    ) -> None:
        """Log an action with context."""
        event = AuditEvent(
            action=action,
            category=category,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            metadata=metadata or {},
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")
            event.user_role = user_context.get("role")

        if request_context:
            event.ip_address = request_context.get("ip_address")
            event.user_agent = request_context.get("user_agent")
            event.session_id = request_context.get("session_id")

        await self.log(event)

    async def log_modification(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        before: Any,
        after: Any,
        user_context: Optional[dict] = None,
    ) -> None:
        """Log a data modification with before/after state."""
        event = AuditEvent(
            action=action,
            category=AuditCategory.DATA_MODIFICATION,
            resource_type=resource_type,
            resource_id=resource_id,
            result=AuditResult.SUCCESS,
            before=before if isinstance(before, dict) else {"value": str(before)},
            after=after if isinstance(after, dict) else {"value": str(after)},
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")

        await self.log(event)

    async def log_failure(
        self,
        action: AuditAction,
        category: AuditCategory,
        resource_type: str,
        resource_id: str,
        error_message: str,
        user_context: Optional[dict] = None,
    ) -> None:
        """Log a failed operation."""
        event = AuditEvent(
            action=action,
            category=category,
            resource_type=resource_type,
            resource_id=resource_id,
            result=AuditResult.FAILURE,
            error_message=error_message,
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")

        await self.log(event)


# FastAPI middleware for audit context
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture request context for audit logging."""

    async def dispatch(self, request: Request, call_next):
        # Extract context for audit logging
        request.state.audit_context = {
            "ip_address": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "session_id": request.headers.get("x-session-id"),
        }

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
```

### 6. Create `/infrastructure/kubernetes/audit/elasticsearch-index.yaml`
```yaml
# Elasticsearch index template for audit logs
apiVersion: v1
kind: ConfigMap
metadata:
  name: audit-index-template
  namespace: aswa-production
data:
  template.json: |
    {
      "index_patterns": ["audit-*"],
      "settings": {
        "number_of_shards": 3,
        "number_of_replicas": 2,
        "index.lifecycle.name": "audit-retention",
        "index.lifecycle.rollover_alias": "audit"
      },
      "mappings": {
        "properties": {
          "id": { "type": "keyword" },
          "timestamp": { "type": "date" },
          "tenant_id": { "type": "keyword" },
          "user_id": { "type": "keyword" },
          "user_email": { "type": "keyword" },
          "user_role": { "type": "keyword" },
          "action": { "type": "keyword" },
          "category": { "type": "keyword" },
          "resource_type": { "type": "keyword" },
          "resource_id": { "type": "keyword" },
          "result": { "type": "keyword" },
          "ip_address": { "type": "ip" },
          "user_agent": { "type": "text" },
          "session_id": { "type": "keyword" },
          "trace_id": { "type": "keyword" },
          "metadata": { "type": "object", "enabled": true },
          "before": { "type": "object", "enabled": false },
          "after": { "type": "object", "enabled": false },
          "error_message": { "type": "text" },
          "hash": { "type": "keyword" }
        }
      }
    }
---
# ILM policy for audit log retention
apiVersion: v1
kind: ConfigMap
metadata:
  name: audit-ilm-policy
  namespace: aswa-production
data:
  policy.json: |
    {
      "policy": {
        "phases": {
          "hot": {
            "min_age": "0ms",
            "actions": {
              "rollover": {
                "max_size": "50gb",
                "max_age": "1d"
              },
              "set_priority": {
                "priority": 100
              }
            }
          },
          "warm": {
            "min_age": "7d",
            "actions": {
              "shrink": {
                "number_of_shards": 1
              },
              "forcemerge": {
                "max_num_segments": 1
              },
              "set_priority": {
                "priority": 50
              }
            }
          },
          "cold": {
            "min_age": "30d",
            "actions": {
              "freeze": {},
              "set_priority": {
                "priority": 0
              }
            }
          },
          "delete": {
            "min_age": "365d",
            "actions": {
              "delete": {}
            }
          }
        }
      }
    }
```

## Test Requirements

Create tests:

1. **AuditServiceTest.java** - Test audit event creation and logging
2. **AuditEventTest.java** - Test event serialization and hashing
3. **test_audit.py** - Python audit logging tests
4. **Integration tests** - Verify Kafka and Elasticsearch integration

## Verification

1. Run tests: `./gradlew test` and `pytest`
2. Verify audit events in Elasticsearch
3. Test audit log integrity verification
4. Verify searchability of audit logs
5. Test retention policy
