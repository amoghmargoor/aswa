package com.aswa.common.audit;

import java.time.Instant;
import java.util.List;

/**
 * Criteria for searching audit events.
 */
public record AuditSearchCriteria(
    String tenantId,
    String userId,
    List<AuditAction> actions,
    List<AuditCategory> categories,
    List<AuditResult> results,
    String resourceType,
    String resourceId,
    Instant startTime,
    Instant endTime,
    String ipAddress,
    int offset,
    int limit
) {

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String tenantId;
        private String userId;
        private List<AuditAction> actions;
        private List<AuditCategory> categories;
        private List<AuditResult> results;
        private String resourceType;
        private String resourceId;
        private Instant startTime;
        private Instant endTime;
        private String ipAddress;
        private int offset = 0;
        private int limit = 100;

        public Builder tenantId(String tenantId) { this.tenantId = tenantId; return this; }
        public Builder userId(String userId) { this.userId = userId; return this; }
        public Builder actions(List<AuditAction> actions) { this.actions = actions; return this; }
        public Builder categories(List<AuditCategory> categories) { this.categories = categories; return this; }
        public Builder results(List<AuditResult> results) { this.results = results; return this; }
        public Builder resourceType(String resourceType) { this.resourceType = resourceType; return this; }
        public Builder resourceId(String resourceId) { this.resourceId = resourceId; return this; }
        public Builder startTime(Instant startTime) { this.startTime = startTime; return this; }
        public Builder endTime(Instant endTime) { this.endTime = endTime; return this; }
        public Builder ipAddress(String ipAddress) { this.ipAddress = ipAddress; return this; }
        public Builder offset(int offset) { this.offset = offset; return this; }
        public Builder limit(int limit) { this.limit = limit; return this; }

        public AuditSearchCriteria build() {
            return new AuditSearchCriteria(tenantId, userId, actions, categories, results,
                resourceType, resourceId, startTime, endTime, ipAddress, offset, limit);
        }
    }
}
