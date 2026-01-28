package com.aswa.common.auth.mfa;

/**
 * OTP (One-Time Password) service for SMS and Email.
 */
public interface OtpService {

    /**
     * Send OTP via SMS or Email.
     *
     * @param challengeId the MFA challenge ID
     * @param method the MFA method (SMS or EMAIL)
     * @param destination phone number or email address
     */
    void sendOtp(String challengeId, MfaMethod method, String destination);

    /**
     * Verify OTP code.
     *
     * @param challengeId the MFA challenge ID
     * @param code the OTP code
     * @return true if valid
     */
    boolean verifyOtp(String challengeId, String code);
}
