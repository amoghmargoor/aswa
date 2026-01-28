package com.aswa.common.security.scanning;

/**
 * Interface for security alert notifications.
 */
public interface SecurityAlertService {

    /**
     * Send critical vulnerability alert.
     */
    void sendCriticalAlert(SecurityScanService.ScanResult result);

    /**
     * Send high severity alert.
     */
    void sendHighSeverityAlert(SecurityScanService.ScanResult result);

    /**
     * Send daily summary.
     */
    void sendDailySummary(SecurityScanService.VulnerabilitySummary summary);
}
