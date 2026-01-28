package com.aswa.common.compliance;

/**
 * Authentication metrics for security posture.
 */
public record AuthMetrics(
    long totalLogins,
    long failedLogins,
    double mfaAdoptionRate,
    double passwordStrengthScore,
    long sessionCount,
    long expiredSessions
) {

    public double getLoginSuccessRate() {
        if (totalLogins == 0) return 100.0;
        return ((totalLogins - failedLogins) * 100.0) / totalLogins;
    }
}
