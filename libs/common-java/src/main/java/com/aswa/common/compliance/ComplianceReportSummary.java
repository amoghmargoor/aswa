package com.aswa.common.compliance;

import java.time.Instant;

/**
 * Summary view of a compliance report.
 */
public record ComplianceReportSummary(
    String id,
    ComplianceFramework framework,
    ComplianceReport.ReportType type,
    ComplianceReport.ReportStatus status,
    Instant generatedAt,
    double score
) {}
