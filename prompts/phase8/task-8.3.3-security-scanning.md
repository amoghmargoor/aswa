# Task 8.3.3: Audit & Compliance - Security Scanning

## Context

You are implementing audit and compliance for ASWA. Compliance reporting is complete. Now we need automated security scanning.

## Objective

Create security scanning implementation that:
1. Scans dependencies for vulnerabilities
2. Performs static code analysis
3. Scans container images
4. Checks infrastructure configurations
5. Generates security reports

## Requirements

### 1. Create `/.github/workflows/security-scan.yaml`
```yaml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

permissions:
  contents: read
  security-events: write
  actions: read

jobs:
  dependency-scan:
    name: Dependency Vulnerability Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Python dependency scan
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install safety
        run: pip install safety pip-audit

      - name: Scan Python dependencies
        run: |
          for service in ingestion-service query-service insight-service; do
            echo "Scanning $service..."
            cd services/$service
            pip-audit --requirement requirements.txt --format json > ../../security-reports/pip-audit-$service.json || true
            cd ../..
          done
        continue-on-error: true

      # Java dependency scan
      - name: Set up Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'

      - name: Run OWASP Dependency Check
        uses: dependency-check/Dependency-Check_Action@main
        with:
          project: 'ASWA'
          path: '.'
          format: 'SARIF'
          out: 'security-reports'
          args: >
            --enableExperimental
            --suppression suppression.xml

      - name: Upload OWASP results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: security-reports/dependency-check-report.sarif

      # Node.js dependency scan
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Audit npm dependencies
        run: |
          cd services/web-dashboard
          npm audit --json > ../../security-reports/npm-audit.json || true
        continue-on-error: true

      - name: Upload scan reports
        uses: actions/upload-artifact@v4
        with:
          name: dependency-scan-reports
          path: security-reports/

  sast-scan:
    name: Static Application Security Testing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # CodeQL Analysis
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: java, python, javascript

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:java,python,javascript"

      # Semgrep scan
      - name: Run Semgrep
        uses: semgrep/semgrep-action@v1
        with:
          config: >-
            p/default
            p/security-audit
            p/owasp-top-ten
            p/cwe-top-25
          generateSarif: true

      - name: Upload Semgrep results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep.sarif

      # Bandit for Python
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r services/ libs/ -f sarif -o bandit-report.sarif || true

      - name: Upload Bandit results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: bandit-report.sarif
        if: always()

  container-scan:
    name: Container Image Scan
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - api-gateway
          - ingestion-service
          - query-service
          - insight-service
          - web-dashboard
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: |
          docker build -t aswa/${{ matrix.service }}:scan \
            -f services/${{ matrix.service }}/Dockerfile \
            --target production .

      # Trivy scan
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'aswa/${{ matrix.service }}:scan'
          format: 'sarif'
          output: 'trivy-${{ matrix.service }}.sarif'
          severity: 'CRITICAL,HIGH,MEDIUM'
          vuln-type: 'os,library'

      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-${{ matrix.service }}.sarif'

      # Grype scan
      - name: Run Grype scanner
        uses: anchore/scan-action@v3
        with:
          image: 'aswa/${{ matrix.service }}:scan'
          fail-build: false
          severity-cutoff: high
          output-format: sarif

      - name: Upload Grype results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif

  infrastructure-scan:
    name: Infrastructure Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Checkov for IaC
      - name: Run Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: infrastructure/
          framework: terraform,kubernetes,dockerfile
          output_format: sarif
          output_file_path: checkov-report.sarif
          soft_fail: true

      - name: Upload Checkov results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: checkov-report.sarif

      # KICS scan
      - name: Run KICS
        uses: checkmarx/kics-github-action@master
        with:
          path: 'infrastructure/'
          output_path: kics-results/
          output_formats: 'sarif'
          enable_comments: true

      - name: Upload KICS results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: kics-results/results.sarif

  secret-scan:
    name: Secret Detection
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Gitleaks
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}

      # TruffleHog
      - name: Run TruffleHog
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ""
          head: HEAD
          extra_args: --only-verified

  security-report:
    name: Generate Security Report
    needs: [dependency-scan, sast-scan, container-scan, infrastructure-scan, secret-scan]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - uses: actions/checkout@v4

      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: all-reports/

      - name: Generate consolidated report
        run: |
          python scripts/generate-security-report.py

      - name: Upload consolidated report
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: security-report.html

      - name: Send notifications
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: 'security-alerts'
          slack-message: |
            ⚠️ Security scan found issues!
            Workflow: ${{ github.workflow }}
            Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 2. Create `/scripts/generate-security-report.py`
```python
#!/usr/bin/env python3
"""Generate consolidated security report from scan results."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def load_sarif(path: Path) -> dict[str, Any]:
    """Load SARIF file."""
    if not path.exists():
        return {"runs": []}
    with open(path) as f:
        return json.load(f)


def extract_findings(sarif: dict) -> list[dict]:
    """Extract findings from SARIF."""
    findings = []
    for run in sarif.get("runs", []):
        tool = run.get("tool", {}).get("driver", {}).get("name", "Unknown")
        for result in run.get("results", []):
            findings.append({
                "tool": tool,
                "rule_id": result.get("ruleId", "Unknown"),
                "message": result.get("message", {}).get("text", ""),
                "level": result.get("level", "warning"),
                "locations": result.get("locations", []),
            })
    return findings


def severity_order(level: str) -> int:
    """Get severity order for sorting."""
    return {"error": 0, "warning": 1, "note": 2}.get(level, 3)


def generate_html_report(findings: list[dict]) -> str:
    """Generate HTML report."""
    # Sort by severity
    findings.sort(key=lambda f: severity_order(f["level"]))

    # Count by severity
    counts = {
        "critical": sum(1 for f in findings if f["level"] == "error"),
        "high": sum(1 for f in findings if f["level"] == "warning"),
        "medium": sum(1 for f in findings if f["level"] == "note"),
    }

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ASWA Security Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ padding: 20px; border-radius: 8px; text-align: center; }}
        .critical {{ background: #fee2e2; color: #dc2626; }}
        .high {{ background: #fef3c7; color: #d97706; }}
        .medium {{ background: #e0f2fe; color: #0284c7; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f3f4f6; }}
        .level-error {{ color: #dc2626; font-weight: bold; }}
        .level-warning {{ color: #d97706; }}
        .level-note {{ color: #0284c7; }}
    </style>
</head>
<body>
    <h1>🔒 ASWA Security Scan Report</h1>
    <p>Generated: {datetime.now().isoformat()}</p>

    <div class="summary">
        <div class="stat critical">
            <h2>{counts['critical']}</h2>
            <p>Critical</p>
        </div>
        <div class="stat high">
            <h2>{counts['high']}</h2>
            <p>High</p>
        </div>
        <div class="stat medium">
            <h2>{counts['medium']}</h2>
            <p>Medium</p>
        </div>
    </div>

    <h2>Findings</h2>
    <table>
        <tr>
            <th>Severity</th>
            <th>Tool</th>
            <th>Rule</th>
            <th>Description</th>
        </tr>
"""

    for finding in findings:
        level_class = f"level-{finding['level']}"
        html += f"""
        <tr>
            <td class="{level_class}">{finding['level'].upper()}</td>
            <td>{finding['tool']}</td>
            <td>{finding['rule_id']}</td>
            <td>{finding['message'][:200]}...</td>
        </tr>
"""

    html += """
    </table>
</body>
</html>
"""
    return html


def main():
    """Main function."""
    reports_dir = Path("all-reports")
    all_findings = []

    # Process all SARIF files
    for sarif_file in reports_dir.rglob("*.sarif"):
        print(f"Processing: {sarif_file}")
        sarif = load_sarif(sarif_file)
        findings = extract_findings(sarif)
        all_findings.extend(findings)

    print(f"Total findings: {len(all_findings)}")

    # Generate HTML report
    html = generate_html_report(all_findings)
    with open("security-report.html", "w") as f:
        f.write(html)

    print("Report generated: security-report.html")

    # Generate JSON summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(all_findings),
        "by_severity": {
            "critical": sum(1 for f in all_findings if f["level"] == "error"),
            "high": sum(1 for f in all_findings if f["level"] == "warning"),
            "medium": sum(1 for f in all_findings if f["level"] == "note"),
        },
        "by_tool": {},
    }

    for f in all_findings:
        tool = f["tool"]
        if tool not in summary["by_tool"]:
            summary["by_tool"][tool] = 0
        summary["by_tool"][tool] += 1

    with open("security-summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/security/scanning/SecurityScanService.java`
```java
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
```

### 4. Create `/suppression.xml` for OWASP Dependency Check
```xml
<?xml version="1.0" encoding="UTF-8"?>
<suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
    <!-- Example suppression for false positives -->
    <suppress>
        <notes>
            False positive - this vulnerability doesn't apply to our usage
        </notes>
        <packageUrl regex="true">^pkg:maven/org\.example/.*$</packageUrl>
        <cve>CVE-XXXX-XXXXX</cve>
    </suppress>

    <!-- Suppress test dependencies -->
    <suppress>
        <notes>Test dependency - not in production</notes>
        <filePath regex="true">.*test.*</filePath>
    </suppress>
</suppressions>
```

### 5. Create `.gitleaks.toml`
```toml
# Gitleaks configuration

title = "ASWA Secret Detection"

[allowlist]
description = "Allowlisted patterns"
paths = [
    '''(.*?)(test|spec)(.*?)\.py$''',
    '''\.md$''',
    '''package-lock\.json$''',
]

[[rules]]
id = "aws-access-key-id"
description = "AWS Access Key ID"
regex = '''(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}'''
tags = ["aws", "key"]

[[rules]]
id = "aws-secret-access-key"
description = "AWS Secret Access Key"
regex = '''(?i)aws(.{0,20})?(?-i)['\"][0-9a-zA-Z\/+]{40}['\"]'''
tags = ["aws", "key"]

[[rules]]
id = "generic-api-key"
description = "Generic API Key"
regex = '''(?i)(api[_-]?key|apikey|api_secret)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,64})['\"]?'''
tags = ["api", "key"]

[[rules]]
id = "jwt-token"
description = "JWT Token"
regex = '''eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*'''
tags = ["jwt", "token"]

[[rules]]
id = "private-key"
description = "Private Key"
regex = '''-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----'''
tags = ["key", "private"]

[[rules]]
id = "password-in-url"
description = "Password in URL"
regex = '''[a-zA-Z]{3,10}://[^/\s:@]{3,20}:[^/\s:@]{3,20}@.{1,100}'''
tags = ["password", "url"]
```

### 6. Create `/services/api-gateway/src/main/java/com/aswa/gateway/controller/SecurityScanController.java`
```java
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
```

## Test Requirements

Create tests:

1. **SecurityScanServiceTest.java** - Test scanning logic
2. **VulnerabilityDetectionTest.java** - Test vulnerability matching
3. **Integration tests** - Test CI pipeline scanning
4. **Report generation tests** - Test HTML/JSON report generation

## Verification

1. Run CI pipeline with security scans
2. Verify SARIF reports are uploaded to GitHub Security
3. Test secret detection
4. Verify container image scanning
5. Check infrastructure scan results
6. Test security report generation
