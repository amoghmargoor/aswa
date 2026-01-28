package com.aswa.common.compliance;

import java.util.List;

/**
 * A section within a compliance report.
 */
public record ComplianceSection(
    String name,
    String description,
    List<ControlAssessment> assessments,
    double score
) {}
