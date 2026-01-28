package com.aswa.common.compliance;

import java.util.List;
import java.util.Optional;

/**
 * Repository for compliance reports.
 */
public interface ComplianceRepository {

    /**
     * Save a compliance report.
     */
    void save(ComplianceReport report);

    /**
     * Find report by ID.
     */
    Optional<ComplianceReport> findById(String id, String tenantId);

    /**
     * List reports for a tenant.
     */
    List<ComplianceReportSummary> listByTenant(
        String tenantId,
        ComplianceFramework framework,
        int page,
        int size
    );

    /**
     * Summary of a compliance report.
     */
    record ComplianceReportSummary(
        String id,
        ComplianceFramework framework,
        ComplianceReport.ReportType type,
        ComplianceReport.ReportStatus status,
        java.time.Instant generatedAt,
        double score
    ) {}
}
