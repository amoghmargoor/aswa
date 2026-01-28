package com.aswa.common.auth.mfa;

/**
 * Supported MFA methods.
 */
public enum MfaMethod {
    TOTP("totp", "Authenticator App", true),
    SMS("sms", "SMS", false),
    EMAIL("email", "Email", false),
    BACKUP_CODE("backup_code", "Backup Code", false);

    private final String code;
    private final String displayName;
    private final boolean primary;

    MfaMethod(String code, String displayName, boolean primary) {
        this.code = code;
        this.displayName = displayName;
        this.primary = primary;
    }

    public String getCode() { return code; }
    public String getDisplayName() { return displayName; }
    public boolean isPrimary() { return primary; }

    public static MfaMethod fromCode(String code) {
        for (MfaMethod method : values()) {
            if (method.code.equals(code)) {
                return method;
            }
        }
        throw new IllegalArgumentException("Unknown MFA method: " + code);
    }
}
