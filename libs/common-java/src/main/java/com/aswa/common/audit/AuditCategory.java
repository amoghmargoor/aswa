package com.aswa.common.audit;

/**
 * Audit event categories.
 */
public enum AuditCategory {
    AUTHENTICATION("authentication", "Authentication events"),
    AUTHORIZATION("authorization", "Authorization events"),
    DATA_ACCESS("data_access", "Data access events"),
    DATA_MODIFICATION("data_modification", "Data modification events"),
    ADMIN("admin", "Administrative events"),
    SECURITY("security", "Security events"),
    SYSTEM("system", "System events");

    private final String code;
    private final String description;

    AuditCategory(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
