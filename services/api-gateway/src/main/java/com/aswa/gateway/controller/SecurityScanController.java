package com.aswa.gateway.controller;

import com.aswa.common.security.scanning.SecurityScanService;
import com.aswa.common.security.scanning.SecurityScanService.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * Security scanning API controller.
 */
@RestController
@RequestMapping("/api/v1/security")
@PreAuthorize("hasRole('ADMIN')")
public class SecurityScanController {

    private final SecurityScanService scanService;

    public SecurityScanController(SecurityScanService scanService) {
        this.scanService = scanService;
    }

    /**
     * Get vulnerability summary.
     */
    @GetMapping("/vulnerabilities/summary")
    public ResponseEntity<VulnerabilitySummary> getSummary() {
        return ResponseEntity.ok(scanService.getSummary());
    }

    /**
     * Run full security scan.
     */
    @PostMapping("/scan")
    public ResponseEntity<ScanResult> runScan() {
        return ResponseEntity.ok(scanService.runFullScan());
    }

    /**
     * Scan specific component.
     */
    @PostMapping("/scan/{component}")
    public ResponseEntity<ScanResult> scanComponent(@PathVariable String component) {
        return ResponseEntity.ok(scanService.scanComponent(component));
    }

    /**
     * Check for critical vulnerabilities.
     */
    @GetMapping("/vulnerabilities/critical")
    public ResponseEntity<CriticalCheckResponse> checkCritical() {
        boolean hasCritical = scanService.hasCriticalVulnerabilities();
        return ResponseEntity.ok(new CriticalCheckResponse(hasCritical));
    }

    public record CriticalCheckResponse(boolean hasCriticalVulnerabilities) {}
}
