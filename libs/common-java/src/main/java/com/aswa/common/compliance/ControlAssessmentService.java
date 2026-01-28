package com.aswa.common.compliance;

import java.time.Instant;
import java.util.List;

/**
 * Service for assessing individual compliance controls.
 */
public interface ControlAssessmentService {

    /**
     * Assess a specific control.
     */
    ControlAssessment assess(String tenantId, String controlId, Instant periodStart, Instant periodEnd);

    /**
     * Get control definition.
     */
    ControlDefinition getControlDefinition(String controlId);

    /**
     * List all controls for a framework.
     */
    List<ControlDefinition> listControls(ComplianceFramework framework);

    /**
     * Control definition.
     */
    record ControlDefinition(
        String id,
        String name,
        String description,
        ComplianceFramework framework,
        List<String> requirements,
        List<String> evidenceTypes
    ) {}
}
