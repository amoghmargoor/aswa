package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Compliance report structure.
 */
public record ComplianceReport(
    String id,
    String tenantId,
    ComplianceFramework framework,
    ReportType type,
    Instant generatedAt,
    Instant periodStart,
    Instant periodEnd,
    String generatedBy,
    ReportStatus status,
    List<ComplianceSection> sections,
    ComplianceSummary summary,
    Map<String, Object> metadata
) {

    public enum ReportType {
        FULL_ASSESSMENT,
        PERIODIC_REVIEW,
        DATA_ACCESS_REPORT,
        SECURITY_POSTURE,
        DATA_RETENTION,
        CUSTOM
    }

    public enum ReportStatus {
        GENERATING,
        COMPLETE,
        FAILED,
        REQUIRES_REVIEW
    }
}
