package com.aswa.common.security.encryption;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.SdkBytes;
import software.amazon.awssdk.services.kms.KmsClient;
import software.amazon.awssdk.services.kms.model.*;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * AWS KMS key management service.
 */
@Service
public class KeyManagementService {

    private static final Logger logger = LoggerFactory.getLogger(KeyManagementService.class);

    private final KmsClient kmsClient;
    private final String masterKeyId;
    private final Map<String, byte[]> keyCache = new ConcurrentHashMap<>();

    public KeyManagementService(
            KmsClient kmsClient,
            @Value("${kms.master-key-id}") String masterKeyId) {
        this.kmsClient = kmsClient;
        this.masterKeyId = masterKeyId;
    }

    /**
     * Get current master key ID.
     */
    public String getCurrentKeyId() {
        return masterKeyId;
    }

    /**
     * Encrypt data encryption key with master key.
     */
    public byte[] encryptDataKey(byte[] dataKey) {
        try {
            EncryptRequest request = EncryptRequest.builder()
                .keyId(masterKeyId)
                .plaintext(SdkBytes.fromByteArray(dataKey))
                .encryptionAlgorithm(EncryptionAlgorithmSpec.SYMMETRIC_DEFAULT)
                .build();

            EncryptResponse response = kmsClient.encrypt(request);
            return response.ciphertextBlob().asByteArray();

        } catch (KmsException e) {
            logger.error("KMS encryption failed: {}", e.getMessage());
            throw new EncryptionException("Failed to encrypt data key", e);
        }
    }

    /**
     * Decrypt data encryption key with master key.
     */
    public byte[] decryptDataKey(byte[] encryptedDataKey) {
        return decryptDataKey(encryptedDataKey, masterKeyId);
    }

    /**
     * Decrypt data encryption key with specific key.
     */
    public byte[] decryptDataKey(byte[] encryptedDataKey, String keyId) {
        try {
            DecryptRequest request = DecryptRequest.builder()
                .keyId(keyId)
                .ciphertextBlob(SdkBytes.fromByteArray(encryptedDataKey))
                .encryptionAlgorithm(EncryptionAlgorithmSpec.SYMMETRIC_DEFAULT)
                .build();

            DecryptResponse response = kmsClient.decrypt(request);
            return response.plaintext().asByteArray();

        } catch (KmsException e) {
            logger.error("KMS decryption failed: {}", e.getMessage());
            throw new EncryptionException("Failed to decrypt data key", e);
        }
    }

    /**
     * Generate a data key using KMS.
     */
    public GeneratedDataKey generateDataKey() {
        try {
            GenerateDataKeyRequest request = GenerateDataKeyRequest.builder()
                .keyId(masterKeyId)
                .keySpec(DataKeySpec.AES_256)
                .build();

            GenerateDataKeyResponse response = kmsClient.generateDataKey(request);

            return new GeneratedDataKey(
                response.plaintext().asByteArray(),
                response.ciphertextBlob().asByteArray(),
                masterKeyId
            );

        } catch (KmsException e) {
            logger.error("KMS data key generation failed: {}", e.getMessage());
            throw new EncryptionException("Failed to generate data key", e);
        }
    }

    /**
     * Rotate to a new key version.
     */
    public void initiateKeyRotation() {
        try {
            // Enable automatic key rotation (annual)
            EnableKeyRotationRequest request = EnableKeyRotationRequest.builder()
                .keyId(masterKeyId)
                .build();

            kmsClient.enableKeyRotation(request);
            logger.info("Key rotation enabled for key: {}", masterKeyId);

        } catch (KmsException e) {
            logger.error("Failed to enable key rotation: {}", e.getMessage());
            throw new EncryptionException("Failed to enable key rotation", e);
        }
    }

    /**
     * Re-encrypt data with new key version.
     */
    public byte[] reEncrypt(byte[] encryptedData, String sourceKeyId) {
        try {
            ReEncryptRequest request = ReEncryptRequest.builder()
                .ciphertextBlob(SdkBytes.fromByteArray(encryptedData))
                .sourceKeyId(sourceKeyId)
                .destinationKeyId(masterKeyId)
                .build();

            ReEncryptResponse response = kmsClient.reEncrypt(request);
            return response.ciphertextBlob().asByteArray();

        } catch (KmsException e) {
            logger.error("KMS re-encryption failed: {}", e.getMessage());
            throw new EncryptionException("Failed to re-encrypt data", e);
        }
    }

    public record GeneratedDataKey(
        byte[] plaintext,
        byte[] ciphertext,
        String keyId
    ) {}
}
