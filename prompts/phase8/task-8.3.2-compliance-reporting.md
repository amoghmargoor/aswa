# Task 8.3.2: Audit & Compliance - Compliance Reporting

## Context

You are implementing audit and compliance for ASWA. Audit logging is complete. Now we need compliance reporting for regulatory requirements.

## Objective

Create compliance reporting that:
1. Generates SOC 2 compliance reports
2. Supports GDPR data access reports
3. Provides security posture dashboards
4. Enables data retention compliance
5. Supports custom compliance frameworks

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/compliance/ComplianceReport.java`
```java
package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Compliance report structure.
 */
public record ComplianceReport(
    String id,
    String tenantId,
    ComplianceFramework framework,
    ReportType type,
    Instant generatedAt,
    Instant periodStart,
    Instant periodEnd,
    String generatedBy,
    ReportStatus status,
    List<ComplianceSection> sections,
    ComplianceSummary summary,
    Map<String, Object> metadata
) {

    public enum ReportType {
        FULL_ASSESSMENT,
        PERIODIC_REVIEW,
        DATA_ACCESS_REPORT,
        SECURITY_POSTURE,
        DATA_RETENTION,
        CUSTOM
    }

    public enum ReportStatus {
        GENERATING,
        COMPLETE,
        FAILED,
        REQUIRES_REVIEW
    }
}
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/compliance/ComplianceFramework.java`
```java
package com.aswa.common.compliance;

import java.util.List;

/**
 * Compliance framework definitions.
 */
public enum ComplianceFramework {
    SOC2_TYPE1("SOC 2 Type I", "Service Organization Control 2 Type I"),
    SOC2_TYPE2("SOC 2 Type II", "Service Organization Control 2 Type II"),
    GDPR("GDPR", "General Data Protection Regulation"),
    HIPAA("HIPAA", "Health Insurance Portability and Accountability Act"),
    PCI_DSS("PCI DSS", "Payment Card Industry Data Security Standard"),
    ISO27001("ISO 27001", "Information Security Management"),
    CCPA("CCPA", "California Consumer Privacy Act"),
    CUSTOM("Custom", "Custom compliance framework");

    private final String name;
    private final String fullName;

    ComplianceFramework(String name, String fullName) {
        this.name = name;
        this.fullName = fullName;
    }

    public String getName() { return name; }
    public String getFullName() { return fullName; }

    public List<String> getRequiredControls() {
        return switch (this) {
            case SOC2_TYPE1, SOC2_TYPE2 -> List.of(
                "CC1.1", "CC1.2", "CC1.3", "CC1.4", "CC1.5",
                "CC2.1", "CC2.2", "CC2.3",
                "CC3.1", "CC3.2", "CC3.3", "CC3.4",
                "CC4.1", "CC4.2",
                "CC5.1", "CC5.2", "CC5.3",
                "CC6.1", "CC6.2", "CC6.3", "CC6.4", "CC6.5", "CC6.6", "CC6.7", "CC6.8",
                "CC7.1", "CC7.2", "CC7.3", "CC7.4", "CC7.5",
                "CC8.1",
                "CC9.1", "CC9.2"
            );
            case GDPR -> List.of(
                "ART5", "ART6", "ART7", "ART12", "ART13", "ART14",
                "ART15", "ART16", "ART17", "ART18", "ART20",
                "ART25", "ART30", "ART32", "ART33", "ART34", "ART35"
            );
            case HIPAA -> List.of(
                "164.308", "164.310", "164.312", "164.314", "164.316"
            );
            default -> List.of();
        };
    }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/compliance/ComplianceService.java`
```java
package com.aswa.common.compliance;

import com.aswa.common.audit.AuditService;
import com.aswa.common.audit.AuditSearchCriteria;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/**
 * Compliance reporting service.
 */
@Service
public class ComplianceService {

    private static final Logger logger = LoggerFactory.getLogger(ComplianceService.class);

    private final AuditService auditService;
    private final ComplianceRepository complianceRepository;
    private final ControlAssessmentService controlAssessmentService;

    public ComplianceService(
            AuditService auditService,
            ComplianceRepository complianceRepository,
            ControlAssessmentService controlAssessmentService) {
        this.auditService = auditService;
        this.complianceRepository = complianceRepository;
        this.controlAssessmentService = controlAssessmentService;
    }

    /**
     * Generate a compliance report.
     */
    public CompletableFuture<ComplianceReport> generateReport(
            String tenantId,
            ComplianceFramework framework,
            ComplianceReport.ReportType type,
            Instant periodStart,
            Instant periodEnd,
            String generatedBy) {

        return CompletableFuture.supplyAsync(() -> {
            String reportId = UUID.randomUUID().toString();

            logger.info("Generating {} report for tenant {}", framework.getName(), tenantId);

            List<ComplianceSection> sections = new ArrayList<>();

            // Generate sections based on framework
            switch (framework) {
                case SOC2_TYPE1, SOC2_TYPE2 -> {
                    sections.add(generateAccessControlSection(tenantId, periodStart, periodEnd));
                    sections.add(generateSecuritySection(tenantId, periodStart, periodEnd));
                    sections.add(generateAvailabilitySection(tenantId, periodStart, periodEnd));
                    sections.add(generateProcessingIntegritySection(tenantId, periodStart, periodEnd));
                    sections.add(generateConfidentialitySection(tenantId, periodStart, periodEnd));
                }
                case GDPR -> {
                    sections.add(generateDataProcessingSection(tenantId, periodStart, periodEnd));
                    sections.add(generateDataSubjectRightsSection(tenantId, periodStart, periodEnd));
                    sections.add(generateDataProtectionSection(tenantId, periodStart, periodEnd));
                    sections.add(generateDataRetentionSection(tenantId, periodStart, periodEnd));
                }
                default -> {
                    sections.add(generateGeneralComplianceSection(tenantId, periodStart, periodEnd));
                }
            }

            // Calculate summary
            ComplianceSummary summary = calculateSummary(sections);

            ComplianceReport report = new ComplianceReport(
                reportId,
                tenantId,
                framework,
                type,
                Instant.now(),
                periodStart,
                periodEnd,
                generatedBy,
                ComplianceReport.ReportStatus.COMPLETE,
                sections,
                summary,
                Map.of()
            );

            // Save report
            complianceRepository.save(report);

            logger.info("Compliance report {} generated successfully", reportId);
            return report;
        });
    }

    /**
     * Generate GDPR data access report (Article 15).
     */
    public CompletableFuture<DataAccessReport> generateDataAccessReport(
            String tenantId,
            String userId,
            String requestedBy) {

        return CompletableFuture.supplyAsync(() -> {
            logger.info("Generating GDPR data access report for user {}", userId);

            // Collect all user data
            List<DataCategory> dataCategories = new ArrayList<>();

            // Personal information
            dataCategories.add(new DataCategory(
                "Personal Information",
                "Name, email, contact details",
                List.of("users.users"),
                "Account creation"
            ));

            // Activity data
            dataCategories.add(new DataCategory(
                "Activity Data",
                "Login history, actions performed",
                List.of("audit.audit_log"),
                "Security and service improvement"
            ));

            // Documents uploaded
            dataCategories.add(new DataCategory(
                "Documents",
                "Uploaded documents and metadata",
                List.of("documents.documents"),
                "Service provision"
            ));

            // Query history
            dataCategories.add(new DataCategory(
                "Query History",
                "Questions asked and responses",
                List.of("queries.query_history"),
                "Service provision"
            ));

            // Get processing activities from audit log
            List<ProcessingActivity> processingActivities = getProcessingActivities(tenantId, userId);

            // Data sharing information
            List<DataSharingRecord> dataSharingRecords = getDataSharingRecords(tenantId, userId);

            return new DataAccessReport(
                UUID.randomUUID().toString(),
                tenantId,
                userId,
                Instant.now(),
                requestedBy,
                dataCategories,
                processingActivities,
                dataSharingRecords,
                getRetentionPolicies(),
                getUserRights()
            );
        });
    }

    /**
     * Generate security posture report.
     */
    public CompletableFuture<SecurityPostureReport> generateSecurityPostureReport(String tenantId) {
        return CompletableFuture.supplyAsync(() -> {
            Instant now = Instant.now();
            Instant thirtyDaysAgo = now.minus(30, ChronoUnit.DAYS);

            // Authentication metrics
            AuthMetrics authMetrics = getAuthMetrics(tenantId, thirtyDaysAgo, now);

            // Access control metrics
            AccessControlMetrics accessMetrics = getAccessControlMetrics(tenantId);

            // Data security metrics
            DataSecurityMetrics dataMetrics = getDataSecurityMetrics(tenantId);

            // Vulnerability metrics
            VulnerabilityMetrics vulnMetrics = getVulnerabilityMetrics(tenantId);

            // Calculate overall score
            int overallScore = calculateSecurityScore(authMetrics, accessMetrics, dataMetrics, vulnMetrics);

            return new SecurityPostureReport(
                UUID.randomUUID().toString(),
                tenantId,
                now,
                overallScore,
                authMetrics,
                accessMetrics,
                dataMetrics,
                vulnMetrics,
                getSecurityRecommendations(overallScore)
            );
        });
    }

    /**
     * Check data retention compliance.
     */
    public CompletableFuture<DataRetentionReport> checkDataRetentionCompliance(String tenantId) {
        return CompletableFuture.supplyAsync(() -> {
            List<RetentionViolation> violations = new ArrayList<>();
            List<RetentionStatus> statuses = new ArrayList<>();

            // Check each data category
            RetentionPolicy auditPolicy = new RetentionPolicy("Audit Logs", 365, ChronoUnit.DAYS);
            RetentionStatus auditStatus = checkRetention(tenantId, "audit_log", auditPolicy);
            statuses.add(auditStatus);
            if (!auditStatus.compliant()) {
                violations.add(new RetentionViolation(
                    "audit_log",
                    auditStatus.oldestRecord(),
                    auditPolicy.retentionDays(),
                    "Data exceeds retention period"
                ));
            }

            // Documents
            RetentionPolicy docPolicy = new RetentionPolicy("Documents", 730, ChronoUnit.DAYS);
            RetentionStatus docStatus = checkRetention(tenantId, "documents", docPolicy);
            statuses.add(docStatus);

            // Query history
            RetentionPolicy queryPolicy = new RetentionPolicy("Query History", 90, ChronoUnit.DAYS);
            RetentionStatus queryStatus = checkRetention(tenantId, "query_history", queryPolicy);
            statuses.add(queryStatus);

            boolean compliant = violations.isEmpty();

            return new DataRetentionReport(
                UUID.randomUUID().toString(),
                tenantId,
                Instant.now(),
                compliant,
                statuses,
                violations
            );
        });
    }

    // Helper methods
    private ComplianceSection generateAccessControlSection(
            String tenantId, Instant start, Instant end) {

        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "CC6.1", start, end),
            controlAssessmentService.assess(tenantId, "CC6.2", start, end),
            controlAssessmentService.assess(tenantId, "CC6.3", start, end)
        );

        return new ComplianceSection(
            "Access Control",
            "Logical and Physical Access Controls",
            assessments,
            calculateSectionScore(assessments)
        );
    }

    private ComplianceSection generateSecuritySection(
            String tenantId, Instant start, Instant end) {

        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "CC7.1", start, end),
            controlAssessmentService.assess(tenantId, "CC7.2", start, end)
        );

        return new ComplianceSection(
            "Security",
            "System Operations and Security",
            assessments,
            calculateSectionScore(assessments)
        );
    }

    // ... Additional helper methods

    private ComplianceSummary calculateSummary(List<ComplianceSection> sections) {
        int total = sections.stream()
            .mapToInt(s -> s.assessments().size())
            .sum();

        int passed = sections.stream()
            .flatMap(s -> s.assessments().stream())
            .filter(a -> a.status() == ControlStatus.PASSED)
            .mapToInt(a -> 1)
            .sum();

        int failed = sections.stream()
            .flatMap(s -> s.assessments().stream())
            .filter(a -> a.status() == ControlStatus.FAILED)
            .mapToInt(a -> 1)
            .sum();

        double score = total > 0 ? (passed * 100.0) / total : 0;

        return new ComplianceSummary(total, passed, failed, total - passed - failed, score);
    }

    private double calculateSectionScore(List<ControlAssessment> assessments) {
        if (assessments.isEmpty()) return 0;
        long passed = assessments.stream()
            .filter(a -> a.status() == ControlStatus.PASSED)
            .count();
        return (passed * 100.0) / assessments.size();
    }

    // Record definitions
    public record DataCategory(String name, String description, List<String> sources, String purpose) {}
    public record ProcessingActivity(String activity, Instant timestamp, String details) {}
    public record DataSharingRecord(String recipient, String purpose, Instant sharedAt) {}
    public record RetentionPolicy(String dataType, int retentionDays, ChronoUnit unit) {}
    public record RetentionViolation(String dataType, Instant oldestRecord, int maxDays, String reason) {}
    public record RetentionStatus(String dataType, boolean compliant, Instant oldestRecord, long recordCount) {}
}
```

### 4. Create `/services/api-gateway/src/main/java/com/aswa/gateway/controller/ComplianceController.java`
```java
package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.compliance.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.time.Instant;
import java.util.concurrent.CompletableFuture;

/**
 * Compliance reporting controller.
 */
@RestController
@RequestMapping("/api/v1/compliance")
@PreAuthorize("hasRole('ADMIN')")
public class ComplianceController {

    private final ComplianceService complianceService;

    public ComplianceController(ComplianceService complianceService) {
        this.complianceService = complianceService;
    }

    /**
     * Generate compliance report.
     */
    @PostMapping("/reports")
    public CompletableFuture<ResponseEntity<ComplianceReport>> generateReport(
            @Valid @RequestBody GenerateReportRequest request,
            @AuthenticationPrincipal UserPrincipal user) {

        return complianceService.generateReport(
            user.getTenantId(),
            request.framework(),
            request.type(),
            request.periodStart(),
            request.periodEnd(),
            user.getEmail()
        ).thenApply(ResponseEntity::ok);
    }

    /**
     * Get compliance report by ID.
     */
    @GetMapping("/reports/{reportId}")
    public ResponseEntity<ComplianceReport> getReport(
            @PathVariable String reportId,
            @AuthenticationPrincipal UserPrincipal user) {

        return complianceService.getReport(reportId, user.getTenantId())
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    /**
     * List compliance reports.
     */
    @GetMapping("/reports")
    public ResponseEntity<List<ComplianceReportSummary>> listReports(
            @RequestParam(required = false) ComplianceFramework framework,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @AuthenticationPrincipal UserPrincipal user) {

        return ResponseEntity.ok(
            complianceService.listReports(user.getTenantId(), framework, page, size)
        );
    }

    /**
     * Generate GDPR data access report.
     */
    @PostMapping("/gdpr/data-access")
    public CompletableFuture<ResponseEntity<DataAccessReport>> generateDataAccessReport(
            @Valid @RequestBody DataAccessRequest request,
            @AuthenticationPrincipal UserPrincipal user) {

        return complianceService.generateDataAccessReport(
            user.getTenantId(),
            request.userId(),
            user.getEmail()
        ).thenApply(ResponseEntity::ok);
    }

    /**
     * Get security posture report.
     */
    @GetMapping("/security-posture")
    public CompletableFuture<ResponseEntity<SecurityPostureReport>> getSecurityPosture(
            @AuthenticationPrincipal UserPrincipal user) {

        return complianceService.generateSecurityPostureReport(user.getTenantId())
            .thenApply(ResponseEntity::ok);
    }

    /**
     * Check data retention compliance.
     */
    @GetMapping("/data-retention")
    public CompletableFuture<ResponseEntity<DataRetentionReport>> checkDataRetention(
            @AuthenticationPrincipal UserPrincipal user) {

        return complianceService.checkDataRetentionCompliance(user.getTenantId())
            .thenApply(ResponseEntity::ok);
    }

    // Request DTOs
    public record GenerateReportRequest(
        ComplianceFramework framework,
        ComplianceReport.ReportType type,
        Instant periodStart,
        Instant periodEnd
    ) {}

    public record DataAccessRequest(String userId) {}
}
```

### 5. Create compliance dashboard configuration

Create `/infrastructure/kubernetes/monitoring/dashboards/aswa-compliance.json`:
```json
{
  "title": "ASWA Compliance Dashboard",
  "uid": "aswa-compliance",
  "panels": [
    {
      "title": "Compliance Score by Framework",
      "type": "gauge",
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
      "targets": [
        {
          "expr": "aswa_compliance_score{framework=\"soc2\"}",
          "legendFormat": "SOC 2"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "min": 0,
          "max": 100,
          "thresholds": {
            "steps": [
              {"color": "red", "value": 0},
              {"color": "yellow", "value": 70},
              {"color": "green", "value": 90}
            ]
          }
        }
      }
    },
    {
      "title": "Failed Login Attempts (24h)",
      "type": "stat",
      "gridPos": {"h": 4, "w": 4, "x": 8, "y": 0},
      "targets": [
        {
          "expr": "sum(increase(audit_events_total{action=\"login_failed\"}[24h]))"
        }
      ]
    },
    {
      "title": "Data Access Requests",
      "type": "stat",
      "gridPos": {"h": 4, "w": 4, "x": 12, "y": 0},
      "targets": [
        {
          "expr": "sum(increase(audit_events_total{category=\"data_access\"}[24h]))"
        }
      ]
    },
    {
      "title": "MFA Adoption Rate",
      "type": "gauge",
      "gridPos": {"h": 4, "w": 4, "x": 16, "y": 0},
      "targets": [
        {
          "expr": "sum(users_mfa_enabled) / sum(users_total) * 100"
        }
      ]
    },
    {
      "title": "Control Status",
      "type": "table",
      "gridPos": {"h": 12, "w": 12, "x": 0, "y": 8},
      "targets": [
        {
          "expr": "aswa_control_status",
          "format": "table"
        }
      ]
    },
    {
      "title": "Audit Events Timeline",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
      "targets": [
        {
          "expr": "sum(rate(audit_events_total[5m])) by (category)",
          "legendFormat": "{{category}}"
        }
      ]
    }
  ]
}
```

## Test Requirements

Create tests:

1. **ComplianceServiceTest.java** - Test report generation
2. **DataAccessReportTest.java** - Test GDPR data access reports
3. **SecurityPostureTest.java** - Test security posture calculation
4. **Integration tests** - Full report generation tests

## Verification

1. Run tests: `./gradlew test`
2. Generate SOC 2 report and verify sections
3. Generate GDPR data access report
4. Verify security posture scoring
5. Check compliance dashboard
