package com.aswa.common.auth.mfa;

import org.apache.commons.codec.binary.Base32;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.crypto.KeyGenerator;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.ByteBuffer;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
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
    private static final int TIME_STEP_SECONDS = 30;
    private static final int ALLOWED_TIME_DRIFT = 1; // Allow 1 step before/after

    private final Base32 base32;
    private final SecureRandom secureRandom;

    public TotpService() {
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
            TIME_STEP_SECONDS
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
            long currentTimeStep = Instant.now().getEpochSecond() / TIME_STEP_SECONDS;

            // Check current time step and allowed drift
            for (int i = -ALLOWED_TIME_DRIFT; i <= ALLOWED_TIME_DRIFT; i++) {
                String expectedCode = generateTotpCode(secret, currentTimeStep + i);
                if (expectedCode.equals(code)) {
                    return true;
                }
            }

            return false;

        } catch (Exception e) {
            logger.warn("TOTP verification failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Generate current TOTP code (for testing).
     */
    public String generateCode(String secret) {
        long currentTimeStep = Instant.now().getEpochSecond() / TIME_STEP_SECONDS;
        return generateTotpCode(secret, currentTimeStep);
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

    private String generateTotpCode(String secret, long timeStep) {
        try {
            byte[] decodedKey = base32.decode(secret);
            SecretKeySpec keySpec = new SecretKeySpec(decodedKey, ALGORITHM);

            Mac mac = Mac.getInstance(ALGORITHM);
            mac.init(keySpec);

            byte[] timeBytes = ByteBuffer.allocate(8).putLong(timeStep).array();
            byte[] hash = mac.doFinal(timeBytes);

            int offset = hash[hash.length - 1] & 0x0f;
            int binary = ((hash[offset] & 0x7f) << 24) |
                        ((hash[offset + 1] & 0xff) << 16) |
                        ((hash[offset + 2] & 0xff) << 8) |
                        (hash[offset + 3] & 0xff);

            int otp = binary % (int) Math.pow(10, CODE_DIGITS);
            return String.format("%0" + CODE_DIGITS + "d", otp);

        } catch (NoSuchAlgorithmException | InvalidKeyException e) {
            throw new RuntimeException("Failed to generate TOTP code", e);
        }
    }
}
