package com.aswa.common.compliance;

/**
 * Data security metrics for security posture.
 */
public record DataSecurityMetrics(
    double encryptionCoverage,
    long encryptedDocuments,
    long unencryptedDocuments,
    boolean tlsEnforced,
    boolean dataClassificationEnabled,
    double piiDetectionCoverage
) {

    public boolean isFullyEncrypted() {
        return unencryptedDocuments == 0;
    }
}
