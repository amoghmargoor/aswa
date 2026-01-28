package com.aswa.common.security.scanning;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * Runtime security scanning service.
 */
@Service
public class SecurityScanService {

    private static final Logger logger = LoggerFactory.getLogger(SecurityScanService.class);

    private final VulnerabilityDatabase vulnerabilityDatabase;
    private final DependencyInventory dependencyInventory;
    private final SecurityAlertService alertService;

    public SecurityScanService(
            VulnerabilityDatabase vulnerabilityDatabase,
            DependencyInventory dependencyInventory,
            SecurityAlertService alertService) {
        this.vulnerabilityDatabase = vulnerabilityDatabase;
        this.dependencyInventory = dependencyInventory;
        this.alertService = alertService;
    }

    /**
     * Run scheduled vulnerability scan.
     */
    @Scheduled(cron = "0 0 3 * * *") // 3 AM daily
    public void scheduledScan() {
        logger.info("Starting scheduled security scan");
        ScanResult result = runFullScan();

        if (result.hasCriticalVulnerabilities()) {
            alertService.sendCriticalAlert(result);
        }

        logger.info("Security scan complete: {} critical, {} high, {} medium",
            result.criticalCount(), result.highCount(), result.mediumCount());
    }

    /**
     * Run full security scan.
     */
    public ScanResult runFullScan() {
        List<Vulnerability> vulnerabilities = new ArrayList<>();

        // Scan dependencies
        for (Dependency dep : dependencyInventory.getAllDependencies()) {
            List<Vulnerability> depVulns = vulnerabilityDatabase.findVulnerabilities(
                dep.name(), dep.version()
            );
            vulnerabilities.addAll(depVulns);
        }

        return new ScanResult(
            UUID.randomUUID().toString(),
            Instant.now(),
            vulnerabilities,
            calculateRiskScore(vulnerabilities)
        );
    }

    /**
     * Scan specific component.
     */
    public ScanResult scanComponent(String componentName) {
        Optional<Dependency> dep = dependencyInventory.getDependency(componentName);
        if (dep.isEmpty()) {
            return ScanResult.empty();
        }

        List<Vulnerability> vulnerabilities = vulnerabilityDatabase.findVulnerabilities(
            dep.get().name(), dep.get().version()
        );

        return new ScanResult(
            UUID.randomUUID().toString(),
            Instant.now(),
            vulnerabilities,
            calculateRiskScore(vulnerabilities)
        );
    }

    /**
     * Check if any critical vulnerabilities exist.
     */
    public boolean hasCriticalVulnerabilities() {
        return runFullScan().hasCriticalVulnerabilities();
    }

    /**
     * Get vulnerability summary.
     */
    public VulnerabilitySummary getSummary() {
        ScanResult result = runFullScan();
        return new VulnerabilitySummary(
            result.criticalCount(),
            result.highCount(),
            result.mediumCount(),
            result.lowCount(),
            result.riskScore()
        );
    }

    private double calculateRiskScore(List<Vulnerability> vulnerabilities) {
        if (vulnerabilities.isEmpty()) return 0.0;

        double score = 0;
        for (Vulnerability v : vulnerabilities) {
            score += switch (v.severity()) {
                case CRITICAL -> 10.0;
                case HIGH -> 7.5;
                case MEDIUM -> 5.0;
                case LOW -> 2.5;
            };
        }
        return Math.min(100, score);
    }

    // Records
    public record ScanResult(
        String id,
        Instant timestamp,
        List<Vulnerability> vulnerabilities,
        double riskScore
    ) {
        public static ScanResult empty() {
            return new ScanResult(UUID.randomUUID().toString(), Instant.now(), List.of(), 0);
        }

        public boolean hasCriticalVulnerabilities() {
            return vulnerabilities.stream().anyMatch(v -> v.severity() == Severity.CRITICAL);
        }

        public long criticalCount() {
            return vulnerabilities.stream().filter(v -> v.severity() == Severity.CRITICAL).count();
        }

        public long highCount() {
            return vulnerabilities.stream().filter(v -> v.severity() == Severity.HIGH).count();
        }

        public long mediumCount() {
            return vulnerabilities.stream().filter(v -> v.severity() == Severity.MEDIUM).count();
        }

        public long lowCount() {
            return vulnerabilities.stream().filter(v -> v.severity() == Severity.LOW).count();
        }
    }

    public record Dependency(String name, String version, String type) {}

    public record Vulnerability(
        String id,
        String cveId,
        String title,
        String description,
        Severity severity,
        String affectedComponent,
        String fixedVersion,
        List<String> references
    ) {}

    public enum Severity {
        CRITICAL, HIGH, MEDIUM, LOW
    }

    public record VulnerabilitySummary(
        long critical,
        long high,
        long medium,
        long low,
        double riskScore
    ) {}
}
