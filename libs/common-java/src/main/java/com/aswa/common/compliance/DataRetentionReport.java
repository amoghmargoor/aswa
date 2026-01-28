package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;

/**
 * Data retention compliance report.
 */
public record DataRetentionReport(
    String id,
    String tenantId,
    Instant generatedAt,
    boolean compliant,
    List<RetentionStatus> statuses,
    List<RetentionViolation> violations
) {

    public record RetentionStatus(
        String dataType,
        boolean compliant,
        Instant oldestRecord,
        long recordCount,
        int maxRetentionDays
    ) {}

    public record RetentionViolation(
        String dataType,
        Instant oldestRecord,
        int maxDays,
        String reason
    ) {}
}
