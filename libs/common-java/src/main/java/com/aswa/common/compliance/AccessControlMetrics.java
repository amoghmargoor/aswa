package com.aswa.common.compliance;

/**
 * Access control metrics for security posture.
 */
public record AccessControlMetrics(
    long totalUsers,
    long activeUsers,
    long adminUsers,
    double rbacCoverage,
    long orphanedPermissions,
    long excessivePermissions
) {

    public double getAdminRatio() {
        if (totalUsers == 0) return 0;
        return (adminUsers * 100.0) / totalUsers;
    }
}
