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
                logger.info("Backup code used for user {}", config.userId());
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
