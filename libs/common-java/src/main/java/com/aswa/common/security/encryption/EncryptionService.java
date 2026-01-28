package com.aswa.common.security.encryption;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-GCM encryption service for data at rest.
 */
@Service
public class EncryptionService {

    private static final Logger logger = LoggerFactory.getLogger(EncryptionService.class);

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int GCM_IV_LENGTH = 12;  // 96 bits
    private static final int GCM_TAG_LENGTH = 128; // bits
    private static final int AES_KEY_SIZE = 256;

    private final KeyManagementService keyManagementService;
    private final SecureRandom secureRandom;

    public EncryptionService(KeyManagementService keyManagementService) {
        this.keyManagementService = keyManagementService;
        this.secureRandom = new SecureRandom();
    }

    /**
     * Encrypt plaintext using envelope encryption.
     */
    public String encrypt(String plaintext) {
        return encrypt(plaintext, null);
    }

    /**
     * Encrypt with encryption context (AAD).
     */
    public String encrypt(String plaintext, String context) {
        try {
            // Generate data encryption key (DEK)
            SecretKey dek = generateDataKey();

            // Encrypt the DEK with master key (envelope encryption)
            byte[] encryptedDek = keyManagementService.encryptDataKey(dek.getEncoded());

            // Encrypt the data with DEK
            byte[] iv = generateIv();
            byte[] ciphertext = encryptWithKey(
                plaintext.getBytes(StandardCharsets.UTF_8),
                dek,
                iv,
                context
            );

            // Package: version (1) + encrypted DEK length (4) + encrypted DEK + IV + ciphertext
            ByteBuffer buffer = ByteBuffer.allocate(
                1 + 4 + encryptedDek.length + GCM_IV_LENGTH + ciphertext.length
            );
            buffer.put((byte) 1); // Version
            buffer.putInt(encryptedDek.length);
            buffer.put(encryptedDek);
            buffer.put(iv);
            buffer.put(ciphertext);

            return Base64.getEncoder().encodeToString(buffer.array());

        } catch (Exception e) {
            logger.error("Encryption failed: {}", e.getMessage());
            throw new EncryptionException("Failed to encrypt data", e);
        }
    }

    /**
     * Decrypt ciphertext.
     */
    public String decrypt(String encryptedData) {
        return decrypt(encryptedData, null);
    }

    /**
     * Decrypt with encryption context.
     */
    public String decrypt(String encryptedData, String context) {
        try {
            byte[] data = Base64.getDecoder().decode(encryptedData);
            ByteBuffer buffer = ByteBuffer.wrap(data);

            // Read version
            byte version = buffer.get();
            if (version != 1) {
                throw new EncryptionException("Unsupported encryption version: " + version);
            }

            // Read encrypted DEK
            int encryptedDekLength = buffer.getInt();
            byte[] encryptedDek = new byte[encryptedDekLength];
            buffer.get(encryptedDek);

            // Read IV
            byte[] iv = new byte[GCM_IV_LENGTH];
            buffer.get(iv);

            // Read ciphertext
            byte[] ciphertext = new byte[buffer.remaining()];
            buffer.get(ciphertext);

            // Decrypt DEK with master key
            byte[] dekBytes = keyManagementService.decryptDataKey(encryptedDek);
            SecretKey dek = new SecretKeySpec(dekBytes, ALGORITHM);

            // Decrypt data with DEK
            byte[] plaintext = decryptWithKey(ciphertext, dek, iv, context);

            return new String(plaintext, StandardCharsets.UTF_8);

        } catch (Exception e) {
            logger.error("Decryption failed: {}", e.getMessage());
            throw new EncryptionException("Failed to decrypt data", e);
        }
    }

    /**
     * Encrypt bytes directly (for file encryption).
     */
    public EncryptedData encryptBytes(byte[] data, String context) {
        try {
            SecretKey dek = generateDataKey();
            byte[] encryptedDek = keyManagementService.encryptDataKey(dek.getEncoded());
            byte[] iv = generateIv();
            byte[] ciphertext = encryptWithKey(data, dek, iv, context);

            return new EncryptedData(
                ciphertext,
                encryptedDek,
                iv,
                keyManagementService.getCurrentKeyId()
            );
        } catch (Exception e) {
            throw new EncryptionException("Failed to encrypt bytes", e);
        }
    }

    /**
     * Decrypt bytes.
     */
    public byte[] decryptBytes(EncryptedData encryptedData, String context) {
        try {
            byte[] dekBytes = keyManagementService.decryptDataKey(
                encryptedData.encryptedKey(),
                encryptedData.keyId()
            );
            SecretKey dek = new SecretKeySpec(dekBytes, ALGORITHM);

            return decryptWithKey(
                encryptedData.ciphertext(),
                dek,
                encryptedData.iv(),
                context
            );
        } catch (Exception e) {
            throw new EncryptionException("Failed to decrypt bytes", e);
        }
    }

    private SecretKey generateDataKey() throws Exception {
        KeyGenerator keyGen = KeyGenerator.getInstance(ALGORITHM);
        keyGen.init(AES_KEY_SIZE, secureRandom);
        return keyGen.generateKey();
    }

    private byte[] generateIv() {
        byte[] iv = new byte[GCM_IV_LENGTH];
        secureRandom.nextBytes(iv);
        return iv;
    }

    private byte[] encryptWithKey(byte[] plaintext, SecretKey key, byte[] iv, String context)
            throws Exception {
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
        cipher.init(Cipher.ENCRYPT_MODE, key, spec);

        if (context != null) {
            cipher.updateAAD(context.getBytes(StandardCharsets.UTF_8));
        }

        return cipher.doFinal(plaintext);
    }

    private byte[] decryptWithKey(byte[] ciphertext, SecretKey key, byte[] iv, String context)
            throws Exception {
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
        cipher.init(Cipher.DECRYPT_MODE, key, spec);

        if (context != null) {
            cipher.updateAAD(context.getBytes(StandardCharsets.UTF_8));
        }

        return cipher.doFinal(ciphertext);
    }

    public record EncryptedData(
        byte[] ciphertext,
        byte[] encryptedKey,
        byte[] iv,
        String keyId
    ) {}
}
