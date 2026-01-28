package com.aswa.common.audit;

/**
 * Audit result types.
 */
public enum AuditResult {
    SUCCESS("success", "Operation succeeded"),
    FAILURE("failure", "Operation failed"),
    DENIED("denied", "Access denied");

    private final String code;
    private final String description;

    AuditResult(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
