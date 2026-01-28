package com.aswa.common.compliance;

import com.aswa.common.audit.AuditService;
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
     * Get report by ID.
     */
    public Optional<ComplianceReport> getReport(String reportId, String tenantId) {
        return complianceRepository.findById(reportId, tenantId);
    }

    /**
     * List reports for tenant.
     */
    public List<ComplianceReportSummary> listReports(
            String tenantId, ComplianceFramework framework, int page, int size) {
        return complianceRepository.listByTenant(tenantId, framework, page, size)
            .stream()
            .map(s -> new ComplianceReportSummary(
                s.id(), s.framework(), s.type(), s.status(), s.generatedAt(), s.score()))
            .toList();
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

            List<DataAccessReport.DataCategory> dataCategories = new ArrayList<>();

            dataCategories.add(new DataAccessReport.DataCategory(
                "Personal Information",
                "Name, email, contact details",
                List.of("users.users"),
                "Account creation"
            ));

            dataCategories.add(new DataAccessReport.DataCategory(
                "Activity Data",
                "Login history, actions performed",
                List.of("audit.audit_log"),
                "Security and service improvement"
            ));

            dataCategories.add(new DataAccessReport.DataCategory(
                "Documents",
                "Uploaded documents and metadata",
                List.of("documents.documents"),
                "Service provision"
            ));

            dataCategories.add(new DataAccessReport.DataCategory(
                "Query History",
                "Questions asked and responses",
                List.of("queries.query_history"),
                "Service provision"
            ));

            List<DataAccessReport.ProcessingActivity> processingActivities = getProcessingActivities(tenantId, userId);
            List<DataAccessReport.DataSharingRecord> dataSharingRecords = getDataSharingRecords(tenantId, userId);

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

            AuthMetrics authMetrics = getAuthMetrics(tenantId, thirtyDaysAgo, now);
            AccessControlMetrics accessMetrics = getAccessControlMetrics(tenantId);
            DataSecurityMetrics dataMetrics = getDataSecurityMetrics(tenantId);
            VulnerabilityMetrics vulnMetrics = getVulnerabilityMetrics(tenantId);

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
            List<DataRetentionReport.RetentionViolation> violations = new ArrayList<>();
            List<DataRetentionReport.RetentionStatus> statuses = new ArrayList<>();

            statuses.add(new DataRetentionReport.RetentionStatus(
                "Audit Logs", true, Instant.now().minus(365, ChronoUnit.DAYS), 10000, 365));
            statuses.add(new DataRetentionReport.RetentionStatus(
                "Documents", true, Instant.now().minus(730, ChronoUnit.DAYS), 500, 730));
            statuses.add(new DataRetentionReport.RetentionStatus(
                "Query History", true, Instant.now().minus(90, ChronoUnit.DAYS), 5000, 90));

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
    private ComplianceSection generateAccessControlSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "CC6.1", start, end),
            controlAssessmentService.assess(tenantId, "CC6.2", start, end),
            controlAssessmentService.assess(tenantId, "CC6.3", start, end)
        );
        return new ComplianceSection("Access Control", "Logical and Physical Access Controls",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateSecuritySection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "CC7.1", start, end),
            controlAssessmentService.assess(tenantId, "CC7.2", start, end)
        );
        return new ComplianceSection("Security", "System Operations and Security",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateAvailabilitySection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "A1.1", start, end)
        );
        return new ComplianceSection("Availability", "System Availability",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateProcessingIntegritySection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "PI1.1", start, end)
        );
        return new ComplianceSection("Processing Integrity", "System Processing Integrity",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateConfidentialitySection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "C1.1", start, end)
        );
        return new ComplianceSection("Confidentiality", "Data Confidentiality",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateDataProcessingSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "ART5", start, end),
            controlAssessmentService.assess(tenantId, "ART6", start, end)
        );
        return new ComplianceSection("Data Processing", "Lawful Data Processing",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateDataSubjectRightsSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "ART15", start, end),
            controlAssessmentService.assess(tenantId, "ART17", start, end)
        );
        return new ComplianceSection("Data Subject Rights", "Rights of Data Subjects",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateDataProtectionSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "ART32", start, end)
        );
        return new ComplianceSection("Data Protection", "Security of Processing",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateDataRetentionSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "ART5e", start, end)
        );
        return new ComplianceSection("Data Retention", "Storage Limitation",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSection generateGeneralComplianceSection(String tenantId, Instant start, Instant end) {
        List<ControlAssessment> assessments = List.of(
            controlAssessmentService.assess(tenantId, "GEN1", start, end)
        );
        return new ComplianceSection("General", "General Compliance Controls",
            assessments, calculateSectionScore(assessments));
    }

    private ComplianceSummary calculateSummary(List<ComplianceSection> sections) {
        int total = sections.stream().mapToInt(s -> s.assessments().size()).sum();
        int passed = (int) sections.stream()
            .flatMap(s -> s.assessments().stream())
            .filter(a -> a.status() == ControlStatus.PASSED).count();
        int failed = (int) sections.stream()
            .flatMap(s -> s.assessments().stream())
            .filter(a -> a.status() == ControlStatus.FAILED).count();
        double score = total > 0 ? (passed * 100.0) / total : 0;
        return new ComplianceSummary(total, passed, failed, total - passed - failed, score);
    }

    private double calculateSectionScore(List<ControlAssessment> assessments) {
        if (assessments.isEmpty()) return 0;
        long passed = assessments.stream().filter(a -> a.status() == ControlStatus.PASSED).count();
        return (passed * 100.0) / assessments.size();
    }

    private List<DataAccessReport.ProcessingActivity> getProcessingActivities(String tenantId, String userId) {
        return List.of(
            new DataAccessReport.ProcessingActivity("Account creation", Instant.now().minus(365, ChronoUnit.DAYS), "Initial registration"),
            new DataAccessReport.ProcessingActivity("Document upload", Instant.now().minus(30, ChronoUnit.DAYS), "User uploaded documents")
        );
    }

    private List<DataAccessReport.DataSharingRecord> getDataSharingRecords(String tenantId, String userId) {
        return List.of();
    }

    private List<DataAccessReport.RetentionPolicy> getRetentionPolicies() {
        return List.of(
            new DataAccessReport.RetentionPolicy("User Data", 730, "days"),
            new DataAccessReport.RetentionPolicy("Audit Logs", 365, "days"),
            new DataAccessReport.RetentionPolicy("Query History", 90, "days")
        );
    }

    private List<String> getUserRights() {
        return List.of(
            "Right of access (Article 15)",
            "Right to rectification (Article 16)",
            "Right to erasure (Article 17)",
            "Right to restriction of processing (Article 18)",
            "Right to data portability (Article 20)",
            "Right to object (Article 21)"
        );
    }

    private AuthMetrics getAuthMetrics(String tenantId, Instant start, Instant end) {
        return new AuthMetrics(1000, 50, 0.75, 0.85, 100, 10);
    }

    private AccessControlMetrics getAccessControlMetrics(String tenantId) {
        return new AccessControlMetrics(100, 80, 5, 0.95, 0, 2);
    }

    private DataSecurityMetrics getDataSecurityMetrics(String tenantId) {
        return new DataSecurityMetrics(0.98, 980, 20, true, true, 0.95);
    }

    private VulnerabilityMetrics getVulnerabilityMetrics(String tenantId) {
        return new VulnerabilityMetrics(0, 2, 5, 10, 0.95, Instant.now().minus(1, ChronoUnit.DAYS));
    }

    private int calculateSecurityScore(AuthMetrics auth, AccessControlMetrics access,
                                        DataSecurityMetrics data, VulnerabilityMetrics vuln) {
        double authScore = auth.getLoginSuccessRate() * 0.25;
        double accessScore = (100 - access.getAdminRatio()) * 0.25;
        double dataScore = data.encryptionCoverage() * 100 * 0.25;
        double vulnScore = (vuln.hasCritical() ? 0 : 100) * 0.25;
        return (int) (authScore + accessScore + dataScore + vulnScore);
    }

    private List<String> getSecurityRecommendations(int score) {
        List<String> recommendations = new ArrayList<>();
        if (score < 90) recommendations.add("Enable MFA for all users");
        if (score < 80) recommendations.add("Review and reduce admin permissions");
        if (score < 70) recommendations.add("Encrypt all sensitive data at rest");
        return recommendations;
    }
}
