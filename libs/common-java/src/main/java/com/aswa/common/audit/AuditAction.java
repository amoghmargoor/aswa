package com.aswa.common.audit;

/**
 * Audit action types.
 */
public enum AuditAction {
    // Authentication
    LOGIN("login", "User login"),
    LOGOUT("logout", "User logout"),
    LOGIN_FAILED("login_failed", "Failed login attempt"),
    PASSWORD_CHANGE("password_change", "Password changed"),
    PASSWORD_RESET("password_reset", "Password reset requested"),
    MFA_ENABLED("mfa_enabled", "MFA enabled"),
    MFA_DISABLED("mfa_disabled", "MFA disabled"),
    SESSION_REVOKED("session_revoked", "Session revoked"),

    // Resource operations
    CREATE("create", "Resource created"),
    READ("read", "Resource accessed"),
    UPDATE("update", "Resource updated"),
    DELETE("delete", "Resource deleted"),
    EXPORT("export", "Data exported"),
    IMPORT("import", "Data imported"),

    // Document operations
    DOCUMENT_UPLOAD("document_upload", "Document uploaded"),
    DOCUMENT_DOWNLOAD("document_download", "Document downloaded"),
    DOCUMENT_PROCESS("document_process", "Document processed"),
    DOCUMENT_DELETE("document_delete", "Document deleted"),

    // Query operations
    QUERY_EXECUTE("query_execute", "Query executed"),
    INSIGHT_GENERATE("insight_generate", "Insight generated"),

    // Admin operations
    USER_CREATE("user_create", "User created"),
    USER_UPDATE("user_update", "User updated"),
    USER_DELETE("user_delete", "User deleted"),
    ROLE_CHANGE("role_change", "User role changed"),
    PERMISSION_GRANT("permission_grant", "Permission granted"),
    PERMISSION_REVOKE("permission_revoke", "Permission revoked"),

    // System operations
    CONFIG_CHANGE("config_change", "Configuration changed"),
    API_KEY_CREATE("api_key_create", "API key created"),
    API_KEY_REVOKE("api_key_revoke", "API key revoked"),
    WEBHOOK_CREATE("webhook_create", "Webhook created"),
    INTEGRATION_ENABLE("integration_enable", "Integration enabled");

    private final String code;
    private final String description;

    AuditAction(String code, String description) {
        this.code = code;
        this.description = description;
    }

    public String getCode() { return code; }
    public String getDescription() { return description; }
}
