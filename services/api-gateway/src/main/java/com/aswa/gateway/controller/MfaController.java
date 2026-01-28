package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.mfa.*;
import com.aswa.common.auth.mfa.MfaService.*;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;

/**
 * MFA management controller.
 */
@RestController
@RequestMapping("/api/v1/mfa")
@Tag(name = "MFA", description = "Multi-factor authentication endpoints")
public class MfaController {

    private final MfaService mfaService;

    public MfaController(MfaService mfaService) {
        this.mfaService = mfaService;
    }

    /**
     * Initiate TOTP enrollment.
     */
    @PostMapping("/totp/enroll")
    @Operation(summary = "Initiate TOTP enrollment", description = "Start TOTP authenticator app setup")
    public ResponseEntity<TotpEnrollmentResponse> initiateTotpEnrollment(
            @AuthenticationPrincipal UserPrincipal user) {

        TotpEnrollmentResponse response = mfaService.initiateTotpEnrollment(user);
        return ResponseEntity.ok(response);
    }

    /**
     * Complete TOTP enrollment.
     */
    @PostMapping("/totp/verify")
    @Operation(summary = "Complete TOTP enrollment", description = "Verify TOTP code to complete setup")
    public ResponseEntity<MfaEnrollmentResult> completeTotpEnrollment(
            @AuthenticationPrincipal UserPrincipal user,
            @Valid @RequestBody TotpVerifyRequest request) {

        MfaEnrollmentResult result = mfaService.completeTotpEnrollment(
            user, request.enrollmentId(), request.code()
        );

        if (result.success()) {
            return ResponseEntity.ok(result);
        }
        return ResponseEntity.badRequest().body(result);
    }

    /**
     * Verify MFA code during login.
     */
    @PostMapping("/verify")
    @Operation(summary = "Verify MFA code", description = "Verify MFA code during login")
    public ResponseEntity<MfaVerificationResult> verify(
            @Valid @RequestBody MfaVerifyRequest request) {

        MfaVerificationResult result = mfaService.verify(
            request.challengeId(),
            MfaMethod.fromCode(request.method()),
            request.code()
        );

        if (result.success()) {
            return ResponseEntity.ok(result);
        }
        return ResponseEntity.status(401).body(result);
    }

    /**
     * Request OTP send (SMS/Email).
     */
    @PostMapping("/send-otp")
    @Operation(summary = "Send OTP", description = "Send OTP via SMS or Email")
    public ResponseEntity<Void> sendOtp(@Valid @RequestBody SendOtpRequest request) {
        mfaService.sendOtp(request.challengeId(), MfaMethod.fromCode(request.method()));
        return ResponseEntity.ok().build();
    }

    /**
     * Disable MFA.
     */
    @DeleteMapping
    @Operation(summary = "Disable MFA", description = "Disable multi-factor authentication")
    public ResponseEntity<Void> disable(
            @AuthenticationPrincipal UserPrincipal user,
            @Valid @RequestBody DisableMfaRequest request) {

        mfaService.disable(user, request.password());
        return ResponseEntity.noContent().build();
    }

    // Request DTOs
    public record TotpVerifyRequest(
        @NotBlank String enrollmentId,
        @NotBlank String code
    ) {}

    public record MfaVerifyRequest(
        @NotBlank String challengeId,
        @NotBlank String method,
        @NotBlank String code
    ) {}

    public record SendOtpRequest(
        @NotBlank String challengeId,
        @NotBlank String method
    ) {}

    public record DisableMfaRequest(
        @NotBlank String password
    ) {}
}
