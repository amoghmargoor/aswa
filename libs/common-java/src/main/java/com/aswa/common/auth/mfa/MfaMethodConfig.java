package com.aswa.common.auth.mfa;

import java.time.Instant;
import java.util.List;

/**
 * Configuration for a specific MFA method.
 */
public record MfaMethodConfig(
    MfaMethod method,
    boolean verified,
    Instant verifiedAt,
    String encryptedSecret,    // For TOTP
    String phoneNumber,         // For SMS
    String email,               // For Email OTP
    List<String> backupCodes,   // For backup codes (hashed)
    int backupCodesRemaining
) {}
