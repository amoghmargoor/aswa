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
