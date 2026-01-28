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
    <h1>ASWA Security Scan Report</h1>
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
        message = finding['message'][:200] + "..." if len(finding['message']) > 200 else finding['message']
        html += f"""
        <tr>
            <td class="{level_class}">{finding['level'].upper()}</td>
            <td>{finding['tool']}</td>
            <td>{finding['rule_id']}</td>
            <td>{message}</td>
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
