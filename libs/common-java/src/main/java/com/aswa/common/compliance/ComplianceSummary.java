package com.aswa.common.compliance;

/**
 * Summary of compliance report results.
 */
public record ComplianceSummary(
    int totalControls,
    int passedControls,
    int failedControls,
    int partialControls,
    double overallScore
) {

    public boolean isCompliant() {
        return failedControls == 0;
    }

    public String getComplianceLevel() {
        if (overallScore >= 95) return "Excellent";
        if (overallScore >= 85) return "Good";
        if (overallScore >= 70) return "Acceptable";
        if (overallScore >= 50) return "Needs Improvement";
        return "Critical";
    }
}
