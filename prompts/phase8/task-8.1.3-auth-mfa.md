# Task 8.1.3: Authentication - Multi-Factor Authentication

## Context

You are implementing authentication for ASWA. Session management is complete. Now we need multi-factor authentication (MFA) support.

## Objective

Create MFA implementation that:
1. Supports TOTP (Time-based One-Time Password)
2. Supports backup/recovery codes
3. Enables SMS and email OTP as fallbacks
4. Implements secure enrollment flow
5. Supports MFA enforcement policies

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/auth/mfa/MfaMethod.java`
```java
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/auth/mfa/TotpService.java`
```java
package com.aswa.common.auth.mfa;

import com.eatthepath.otp.TimeBasedOneTimePasswordGenerator;
import org.apache.commons.codec.binary.Base32;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * TOTP (Time-based One-Time Password) service.
 */
@Service
public class TotpService {

    private static final Logger logger = LoggerFactory.getLogger(TotpService.class);
    private static final String ALGORITHM = "HmacSHA1";
    private static final int CODE_DIGITS = 6;
    private static final Duration TIME_STEP = Duration.ofSeconds(30);
    private static final int ALLOWED_TIME_DRIFT = 1; // Allow 1 step before/after

    private final TimeBasedOneTimePasswordGenerator totpGenerator;
    private final Base32 base32;
    private final SecureRandom secureRandom;

    public TotpService() throws NoSuchAlgorithmException {
        this.totpGenerator = new TimeBasedOneTimePasswordGenerator(TIME_STEP, CODE_DIGITS, ALGORITHM);
        this.base32 = new Base32();
        this.secureRandom = new SecureRandom();
    }

    /**
     * Generate a new TOTP secret.
     */
    public String generateSecret() {
        try {
            KeyGenerator keyGenerator = KeyGenerator.getInstance(ALGORITHM);
            keyGenerator.init(160); // 160 bits for SHA1
            SecretKey key = keyGenerator.generateKey();
            return base32.encodeAsString(key.getEncoded());
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("Failed to generate TOTP secret", e);
        }
    }

    /**
     * Generate TOTP provisioning URI for QR code.
     */
    public String generateProvisioningUri(
            String secret,
            String accountName,
            String issuer) {

        return String.format(
            "otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=%s&digits=%d&period=%d",
            issuer,
            accountName,
            secret,
            issuer,
            "SHA1",
            CODE_DIGITS,
            TIME_STEP.getSeconds()
        );
    }

    /**
     * Verify a TOTP code.
     */
    public boolean verifyCode(String secret, String code) {
        if (secret == null || code == null || code.length() != CODE_DIGITS) {
            return false;
        }

        try {
            SecretKey key = decodeSecret(secret);
            Instant now = Instant.now();

            // Check current time step and allowed drift
            for (int i = -ALLOWED_TIME_DRIFT; i <= ALLOWED_TIME_DRIFT; i++) {
                Instant checkTime = now.plus(TIME_STEP.multipliedBy(i));
                String expectedCode = String.format("%06d", totpGenerator.generateOneTimePassword(key, checkTime));

                if (expectedCode.equals(code)) {
                    return true;
                }
            }

            return false;

        } catch (InvalidKeyException e) {
            logger.warn("Invalid TOTP secret: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Generate current TOTP code (for testing).
     */
    public String generateCode(String secret) {
        try {
            SecretKey key = decodeSecret(secret);
            return String.format("%06d", totpGenerator.generateOneTimePassword(key, Instant.now()));
        } catch (InvalidKeyException e) {
            throw new RuntimeException("Failed to generate TOTP code", e);
        }
    }

    /**
     * Generate backup/recovery codes.
     */
    public List<String> generateBackupCodes(int count) {
        List<String> codes = new ArrayList<>(count);

        for (int i = 0; i < count; i++) {
            byte[] bytes = new byte[5];
            secureRandom.nextBytes(bytes);

            // Format as XXXX-XXXX
            StringBuilder code = new StringBuilder();
            for (int j = 0; j < bytes.length; j++) {
                code.append(String.format("%02x", bytes[j] & 0xff));
                if (j == 2) code.append("-");
            }
            codes.add(code.toString().toUpperCase());
        }

        return codes;
    }

    private SecretKey decodeSecret(String secret) {
        byte[] decoded = base32.decode(secret);
        return new SecretKeySpec(decoded, ALGORITHM);
    }
}
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/auth/mfa/MfaConfiguration.java`
```java
package com.aswa.common.auth.mfa;

import java.time.Instant;
import java.util.List;

/**
 * User's MFA configuration.
 */
public record MfaConfiguration(
    String userId,
    String tenantId,
    boolean enabled,
    MfaMethod preferredMethod,
    List<MfaMethodConfig> methods,
    Instant createdAt,
    Instant updatedAt
) {

    public boolean hasMethod(MfaMethod method) {
        return methods.stream().anyMatch(m -> m.method() == method && m.verified());
    }

    public MfaMethodConfig getMethodConfig(MfaMethod method) {
        return methods.stream()
            .filter(m -> m.method() == method)
            .findFirst()
            .orElse(null);
    }
}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/auth/mfa/MfaMethodConfig.java`
```java
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
```

### 5. Create `/libs/common-java/src/main/java/com/aswa/common/auth/mfa/MfaService.java`
```java
package com.aswa.common.auth.mfa;

import com.aswa.common.auth.UserPrincipal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * MFA management service.
 */
@Service
public class MfaService {

    private static final Logger logger = LoggerFactory.getLogger(MfaService.class);

    private static final int BACKUP_CODE_COUNT = 10;
    private static final String PENDING_ENROLLMENT_PREFIX = "mfa_enrollment:";
    private static final String MFA_CHALLENGE_PREFIX = "mfa_challenge:";
    private static final Duration ENROLLMENT_TTL = Duration.ofMinutes(10);
    private static final Duration CHALLENGE_TTL = Duration.ofMinutes(5);

    private final TotpService totpService;
    private final OtpService otpService;
    private final MfaRepository mfaRepository;
    private final PasswordEncoder passwordEncoder;
    private final RedisTemplate<String, String> redisTemplate;
    private final EncryptionService encryptionService;

    public MfaService(
            TotpService totpService,
            OtpService otpService,
            MfaRepository mfaRepository,
            PasswordEncoder passwordEncoder,
            RedisTemplate<String, String> redisTemplate,
            EncryptionService encryptionService) {
        this.totpService = totpService;
        this.otpService = otpService;
        this.mfaRepository = mfaRepository;
        this.passwordEncoder = passwordEncoder;
        this.redisTemplate = redisTemplate;
        this.encryptionService = encryptionService;
    }

    /**
     * Start TOTP enrollment.
     */
    public TotpEnrollmentResponse initiateTotpEnrollment(UserPrincipal user) {
        String secret = totpService.generateSecret();
        String provisioningUri = totpService.generateProvisioningUri(
            secret,
            user.getEmail(),
            "ASWA"
        );

        // Store pending enrollment in Redis
        String enrollmentId = UUID.randomUUID().toString();
        String key = PENDING_ENROLLMENT_PREFIX + enrollmentId;

        // Store encrypted secret temporarily
        String encryptedSecret = encryptionService.encrypt(secret);
        redisTemplate.opsForValue().set(key, encryptedSecret, ENROLLMENT_TTL.toSeconds(), TimeUnit.SECONDS);

        return new TotpEnrollmentResponse(enrollmentId, secret, provisioningUri);
    }

    /**
     * Complete TOTP enrollment with verification.
     */
    public MfaEnrollmentResult completeTotpEnrollment(
            UserPrincipal user,
            String enrollmentId,
            String verificationCode) {

        String key = PENDING_ENROLLMENT_PREFIX + enrollmentId;
        String encryptedSecret = redisTemplate.opsForValue().get(key);

        if (encryptedSecret == null) {
            return new MfaEnrollmentResult(false, "Enrollment expired", null);
        }

        String secret = encryptionService.decrypt(encryptedSecret);

        // Verify the code
        if (!totpService.verifyCode(secret, verificationCode)) {
            return new MfaEnrollmentResult(false, "Invalid verification code", null);
        }

        // Generate backup codes
        List<String> backupCodes = totpService.generateBackupCodes(BACKUP_CODE_COUNT);
        List<String> hashedBackupCodes = backupCodes.stream()
            .map(passwordEncoder::encode)
            .toList();

        // Save MFA configuration
        MfaMethodConfig totpConfig = new MfaMethodConfig(
            MfaMethod.TOTP,
            true,
            Instant.now(),
            encryptionService.encrypt(secret),
            null,
            null,
            hashedBackupCodes,
            BACKUP_CODE_COUNT
        );

        MfaConfiguration config = getOrCreateConfiguration(user);
        List<MfaMethodConfig> methods = new ArrayList<>(config.methods());
        methods.removeIf(m -> m.method() == MfaMethod.TOTP);
        methods.add(totpConfig);

        MfaConfiguration updated = new MfaConfiguration(
            config.userId(),
            config.tenantId(),
            true,
            MfaMethod.TOTP,
            methods,
            config.createdAt(),
            Instant.now()
        );

        mfaRepository.save(updated);

        // Clean up pending enrollment
        redisTemplate.delete(key);

        logger.info("TOTP enrollment completed for user {}", user.getId());

        return new MfaEnrollmentResult(true, "TOTP enabled successfully", backupCodes);
    }

    /**
     * Create MFA challenge after password verification.
     */
    public MfaChallenge createChallenge(UserPrincipal user) {
        MfaConfiguration config = mfaRepository.findByUserIdAndTenantId(
            user.getId(), user.getTenantId()
        );

        if (config == null || !config.enabled()) {
            return null;
        }

        String challengeId = UUID.randomUUID().toString();

        List<MfaMethod> availableMethods = config.methods().stream()
            .filter(MfaMethodConfig::verified)
            .map(MfaMethodConfig::method)
            .toList();

        // Store challenge in Redis
        String key = MFA_CHALLENGE_PREFIX + challengeId;
        MfaChallengeData data = new MfaChallengeData(
            user.getId(),
            user.getTenantId(),
            availableMethods,
            config.preferredMethod(),
            Instant.now().plus(CHALLENGE_TTL)
        );

        // Serialize and store
        redisTemplate.opsForValue().set(
            key,
            serializeChallengeData(data),
            CHALLENGE_TTL.toSeconds(),
            TimeUnit.SECONDS
        );

        return new MfaChallenge(challengeId, availableMethods, config.preferredMethod());
    }

    /**
     * Verify MFA code.
     */
    public MfaVerificationResult verify(
            String challengeId,
            MfaMethod method,
            String code) {

        String key = MFA_CHALLENGE_PREFIX + challengeId;
        String dataJson = redisTemplate.opsForValue().get(key);

        if (dataJson == null) {
            return new MfaVerificationResult(false, "Challenge expired or invalid");
        }

        MfaChallengeData data = deserializeChallengeData(dataJson);

        if (Instant.now().isAfter(data.expiresAt())) {
            redisTemplate.delete(key);
            return new MfaVerificationResult(false, "Challenge expired");
        }

        MfaConfiguration config = mfaRepository.findByUserIdAndTenantId(
            data.userId(), data.tenantId()
        );

        boolean verified = switch (method) {
            case TOTP -> verifyTotp(config, code);
            case BACKUP_CODE -> verifyBackupCode(config, code);
            case SMS, EMAIL -> otpService.verifyOtp(challengeId, code);
        };

        if (verified) {
            redisTemplate.delete(key);
            logger.info("MFA verification successful for user {}", data.userId());
            return new MfaVerificationResult(true, null);
        }

        return new MfaVerificationResult(false, "Invalid code");
    }

    /**
     * Send OTP via SMS or Email.
     */
    public void sendOtp(String challengeId, MfaMethod method) {
        String key = MFA_CHALLENGE_PREFIX + challengeId;
        String dataJson = redisTemplate.opsForValue().get(key);

        if (dataJson == null) {
            throw new IllegalStateException("Invalid challenge");
        }

        MfaChallengeData data = deserializeChallengeData(dataJson);
        MfaConfiguration config = mfaRepository.findByUserIdAndTenantId(
            data.userId(), data.tenantId()
        );

        MfaMethodConfig methodConfig = config.getMethodConfig(method);
        if (methodConfig == null) {
            throw new IllegalStateException("MFA method not configured");
        }

        otpService.sendOtp(challengeId, method,
            method == MfaMethod.SMS ? methodConfig.phoneNumber() : methodConfig.email());
    }

    /**
     * Disable MFA for user.
     */
    public void disable(UserPrincipal user, String password) {
        // Verify password first
        // authService.verifyPassword(user, password);

        mfaRepository.deleteByUserIdAndTenantId(user.getId(), user.getTenantId());
        logger.info("MFA disabled for user {}", user.getId());
    }

    /**
     * Check if MFA is required for user.
     */
    public boolean isMfaRequired(UserPrincipal user) {
        MfaConfiguration config = mfaRepository.findByUserIdAndTenantId(
            user.getId(), user.getTenantId()
        );
        return config != null && config.enabled();
    }

    private boolean verifyTotp(MfaConfiguration config, String code) {
        MfaMethodConfig totpConfig = config.getMethodConfig(MfaMethod.TOTP);
        if (totpConfig == null) return false;

        String secret = encryptionService.decrypt(totpConfig.encryptedSecret());
        return totpService.verifyCode(secret, code);
    }

    private boolean verifyBackupCode(MfaConfiguration config, String code) {
        MfaMethodConfig backupConfig = config.getMethodConfig(MfaMethod.TOTP);
        if (backupConfig == null || backupConfig.backupCodes().isEmpty()) {
            return false;
        }

        String normalizedCode = code.toUpperCase().replace("-", "");

        for (int i = 0; i < backupConfig.backupCodes().size(); i++) {
            if (passwordEncoder.matches(normalizedCode, backupConfig.backupCodes().get(i))) {
                // Remove used code
                List<String> remainingCodes = new ArrayList<>(backupConfig.backupCodes());
                remainingCodes.remove(i);

                // Update configuration
                // mfaRepository.updateBackupCodes(config.userId(), config.tenantId(), remainingCodes);

                logger.info("Backup code used for user {}, {} remaining",
                    config.userId(), remainingCodes.size());
                return true;
            }
        }

        return false;
    }

    private MfaConfiguration getOrCreateConfiguration(UserPrincipal user) {
        MfaConfiguration existing = mfaRepository.findByUserIdAndTenantId(
            user.getId(), user.getTenantId()
        );

        if (existing != null) {
            return existing;
        }

        return new MfaConfiguration(
            user.getId(),
            user.getTenantId(),
            false,
            null,
            List.of(),
            Instant.now(),
            Instant.now()
        );
    }

    private String serializeChallengeData(MfaChallengeData data) {
        // Use Jackson ObjectMapper in production
        return String.format("%s|%s|%s|%s|%d",
            data.userId(), data.tenantId(),
            String.join(",", data.methods().stream().map(MfaMethod::getCode).toList()),
            data.preferredMethod() != null ? data.preferredMethod().getCode() : "",
            data.expiresAt().toEpochMilli()
        );
    }

    private MfaChallengeData deserializeChallengeData(String json) {
        String[] parts = json.split("\\|");
        List<MfaMethod> methods = Arrays.stream(parts[2].split(","))
            .filter(s -> !s.isEmpty())
            .map(MfaMethod::fromCode)
            .toList();

        return new MfaChallengeData(
            parts[0],
            parts[1],
            methods,
            parts[3].isEmpty() ? null : MfaMethod.fromCode(parts[3]),
            Instant.ofEpochMilli(Long.parseLong(parts[4]))
        );
    }

    // Records
    public record TotpEnrollmentResponse(String enrollmentId, String secret, String provisioningUri) {}
    public record MfaEnrollmentResult(boolean success, String message, List<String> backupCodes) {}
    public record MfaChallenge(String challengeId, List<MfaMethod> availableMethods, MfaMethod preferredMethod) {}
    public record MfaVerificationResult(boolean success, String error) {}
    public record MfaChallengeData(String userId, String tenantId, List<MfaMethod> methods, MfaMethod preferredMethod, Instant expiresAt) {}
}
```

### 6. Create `/services/api-gateway/src/main/java/com/aswa/gateway/controller/MfaController.java`
```java
package com.aswa.gateway.controller;

import com.aswa.common.auth.UserPrincipal;
import com.aswa.common.auth.mfa.*;
import com.aswa.common.auth.mfa.MfaService.*;
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
public class MfaController {

    private final MfaService mfaService;

    public MfaController(MfaService mfaService) {
        this.mfaService = mfaService;
    }

    /**
     * Initiate TOTP enrollment.
     */
    @PostMapping("/totp/enroll")
    public ResponseEntity<TotpEnrollmentResponse> initiateTotpEnrollment(
            @AuthenticationPrincipal UserPrincipal user) {

        TotpEnrollmentResponse response = mfaService.initiateTotpEnrollment(user);
        return ResponseEntity.ok(response);
    }

    /**
     * Complete TOTP enrollment.
     */
    @PostMapping("/totp/verify")
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
    public ResponseEntity<Void> sendOtp(@Valid @RequestBody SendOtpRequest request) {
        mfaService.sendOtp(request.challengeId(), MfaMethod.fromCode(request.method()));
        return ResponseEntity.ok().build();
    }

    /**
     * Disable MFA.
     */
    @DeleteMapping
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
```

## Test Requirements

Create tests in `/services/api-gateway/src/test/java/com/aswa/gateway/mfa/`:

1. **TotpServiceTest.java** - Test TOTP generation and verification
2. **MfaServiceTest.java** - Test MFA enrollment and verification flows
3. **MfaControllerTest.java** - Test API endpoints
4. **BackupCodeTest.java** - Test backup code functionality

## Verification

1. Run tests: `./gradlew test`
2. Test TOTP enrollment with authenticator app
3. Verify backup codes work
4. Test MFA challenge flow
5. Verify rate limiting on verification attempts
