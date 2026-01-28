package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;

/**
 * Security posture report.
 */
public record SecurityPostureReport(
    String id,
    String tenantId,
    Instant generatedAt,
    int overallScore,
    AuthMetrics authMetrics,
    AccessControlMetrics accessControlMetrics,
    DataSecurityMetrics dataSecurityMetrics,
    VulnerabilityMetrics vulnerabilityMetrics,
    List<String> recommendations
) {

    public String getPostureLevel() {
        if (overallScore >= 90) return "Excellent";
        if (overallScore >= 75) return "Good";
        if (overallScore >= 60) return "Fair";
        if (overallScore >= 40) return "Poor";
        return "Critical";
    }
}
