package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.compliance.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.time.Instant;
import java.util.List;
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
