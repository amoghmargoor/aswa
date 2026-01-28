package com.aswa.common.compliance;

/**
 * Status of a compliance control assessment.
 */
public enum ControlStatus {
    PASSED("passed", "Control requirements met"),
    FAILED("failed", "Control requirements not met"),
    PARTIAL("partial", "Control partially implemented"),
    NOT_APPLICABLE("not_applicable", "Control not applicable"),
    NOT_ASSESSED("not_assessed", "Control not yet assessed");

    private final String code;
    private final String description;

    ControlStatus(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
