# Task 8.2.1: Data Security - Encryption at Rest

## Context

You are implementing data security for ASWA. Authentication is complete. Now we need encryption at rest for sensitive data.

## Objective

Create encryption at rest implementation that:
1. Encrypts sensitive data before storage
2. Implements key management with rotation
3. Uses envelope encryption pattern
4. Integrates with AWS KMS
5. Supports field-level encryption

## Requirements

### 1. Create `/libs/common-java/src/main/java/com/aswa/common/security/encryption/EncryptionService.java`
```java
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
```

### 2. Create `/libs/common-java/src/main/java/com/aswa/common/security/encryption/KeyManagementService.java`
```java
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
```

### 3. Create `/libs/common-java/src/main/java/com/aswa/common/security/encryption/FieldEncryption.java`
```java
package com.aswa.common.security.encryption;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * JPA attribute converter for field-level encryption.
 */
@Converter
@Component
public class FieldEncryption implements AttributeConverter<String, String> {

    private static EncryptionService encryptionService;

    @Autowired
    public void setEncryptionService(EncryptionService service) {
        FieldEncryption.encryptionService = service;
    }

    @Override
    public String convertToDatabaseColumn(String attribute) {
        if (attribute == null) {
            return null;
        }
        return encryptionService.encrypt(attribute);
    }

    @Override
    public String convertToEntityAttribute(String dbData) {
        if (dbData == null) {
            return null;
        }
        return encryptionService.decrypt(dbData);
    }
}
```

### 4. Create `/libs/common-java/src/main/java/com/aswa/common/security/encryption/EncryptedField.java`
```java
package com.aswa.common.security.encryption;

import jakarta.persistence.Convert;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Annotation for fields that should be encrypted at rest.
 */
@Target({ElementType.FIELD, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Convert(converter = FieldEncryption.class)
public @interface EncryptedField {
}
```

### 5. Create `/libs/common-python/src/aswa_common/encryption.py`
```python
"""Encryption at rest utilities for Python services."""

import base64
import os
import secrets
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import boto3
from botocore.exceptions import ClientError

import structlog

logger = structlog.get_logger()


class EncryptionService:
    """AES-GCM encryption service with envelope encryption."""

    def __init__(
        self,
        kms_key_id: str | None = None,
        region: str | None = None,
    ):
        self.kms_key_id = kms_key_id or os.environ.get("KMS_KEY_ID")
        self.region = region or os.environ.get("AWS_REGION", "us-west-2")
        self.kms_client = boto3.client("kms", region_name=self.region)

    def encrypt(self, plaintext: str, context: Optional[str] = None) -> str:
        """Encrypt plaintext using envelope encryption."""
        try:
            # Generate data key from KMS
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec="AES_256",
            )

            plaintext_key = response["Plaintext"]
            encrypted_key = response["CiphertextBlob"]

            # Encrypt data with data key
            nonce = secrets.token_bytes(12)
            aesgcm = AESGCM(plaintext_key)

            aad = context.encode() if context else None
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), aad)

            # Package: version + key_len + encrypted_key + nonce + ciphertext
            key_len = len(encrypted_key).to_bytes(4, "big")
            package = b"\x01" + key_len + encrypted_key + nonce + ciphertext

            return base64.b64encode(package).decode()

        except ClientError as e:
            logger.error("Encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt: {e}")

    def decrypt(self, encrypted_data: str, context: Optional[str] = None) -> str:
        """Decrypt ciphertext."""
        try:
            package = base64.b64decode(encrypted_data)

            # Parse package
            version = package[0]
            if version != 1:
                raise EncryptionError(f"Unsupported version: {version}")

            key_len = int.from_bytes(package[1:5], "big")
            encrypted_key = package[5:5 + key_len]
            nonce = package[5 + key_len:5 + key_len + 12]
            ciphertext = package[5 + key_len + 12:]

            # Decrypt data key
            response = self.kms_client.decrypt(
                KeyId=self.kms_key_id,
                CiphertextBlob=encrypted_key,
            )
            plaintext_key = response["Plaintext"]

            # Decrypt data
            aesgcm = AESGCM(plaintext_key)
            aad = context.encode() if context else None
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)

            return plaintext.decode()

        except ClientError as e:
            logger.error("Decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt: {e}")

    def encrypt_bytes(
        self,
        data: bytes,
        context: Optional[str] = None,
    ) -> "EncryptedData":
        """Encrypt raw bytes."""
        try:
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec="AES_256",
            )

            plaintext_key = response["Plaintext"]
            encrypted_key = response["CiphertextBlob"]

            nonce = secrets.token_bytes(12)
            aesgcm = AESGCM(plaintext_key)

            aad = context.encode() if context else None
            ciphertext = aesgcm.encrypt(nonce, data, aad)

            return EncryptedData(
                ciphertext=ciphertext,
                encrypted_key=encrypted_key,
                nonce=nonce,
                key_id=self.kms_key_id,
            )

        except ClientError as e:
            raise EncryptionError(f"Failed to encrypt bytes: {e}")

    def decrypt_bytes(
        self,
        encrypted_data: "EncryptedData",
        context: Optional[str] = None,
    ) -> bytes:
        """Decrypt raw bytes."""
        try:
            response = self.kms_client.decrypt(
                KeyId=encrypted_data.key_id,
                CiphertextBlob=encrypted_data.encrypted_key,
            )
            plaintext_key = response["Plaintext"]

            aesgcm = AESGCM(plaintext_key)
            aad = context.encode() if context else None

            return aesgcm.decrypt(
                encrypted_data.nonce,
                encrypted_data.ciphertext,
                aad,
            )

        except ClientError as e:
            raise EncryptionError(f"Failed to decrypt bytes: {e}")


class EncryptedData:
    """Container for encrypted data components."""

    def __init__(
        self,
        ciphertext: bytes,
        encrypted_key: bytes,
        nonce: bytes,
        key_id: str,
    ):
        self.ciphertext = ciphertext
        self.encrypted_key = encrypted_key
        self.nonce = nonce
        self.key_id = key_id

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "encrypted_key": base64.b64encode(self.encrypted_key).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "key_id": self.key_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedData":
        """Deserialize from dictionary."""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            encrypted_key=base64.b64decode(data["encrypted_key"]),
            nonce=base64.b64decode(data["nonce"]),
            key_id=data["key_id"],
        )


class EncryptionError(Exception):
    """Encryption operation error."""
    pass


# SQLAlchemy type for encrypted fields
from sqlalchemy import TypeDecorator, Text


class EncryptedString(TypeDecorator):
    """SQLAlchemy type for encrypted string fields."""

    impl = Text
    cache_ok = True

    def __init__(self):
        super().__init__()
        self._encryption_service = None

    @property
    def encryption_service(self) -> EncryptionService:
        if self._encryption_service is None:
            self._encryption_service = EncryptionService()
        return self._encryption_service

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.encryption_service.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.encryption_service.decrypt(value)
```

### 6. Create KMS Terraform configuration

Create `/infrastructure/terraform/modules/kms/main.tf`:
```hcl
# KMS key for ASWA data encryption

resource "aws_kms_key" "aswa_data" {
  description             = "ASWA data encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow service access"
        Effect = "Allow"
        Principal = {
          AWS = var.service_role_arns
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "aswa-data-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "aswa_data" {
  name          = "alias/aswa-data-${var.environment}"
  target_key_id = aws_kms_key.aswa_data.key_id
}

# RDS encryption key
resource "aws_kms_key" "rds" {
  description             = "ASWA RDS encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "aswa-rds-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/aswa-rds-${var.environment}"
  target_key_id = aws_kms_key.rds.key_id
}

# S3 encryption key
resource "aws_kms_key" "s3" {
  description             = "ASWA S3 encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "aswa-s3-encryption"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "s3" {
  name          = "alias/aswa-s3-${var.environment}"
  target_key_id = aws_kms_key.s3.key_id
}

output "data_key_id" {
  value = aws_kms_key.aswa_data.key_id
}

output "data_key_arn" {
  value = aws_kms_key.aswa_data.arn
}

output "rds_key_arn" {
  value = aws_kms_key.rds.arn
}

output "s3_key_arn" {
  value = aws_kms_key.s3.arn
}
```

## Test Requirements

Create tests for encryption:

1. **EncryptionServiceTest.java** - Test encryption/decryption
2. **KeyManagementServiceTest.java** - Test KMS operations (with LocalStack)
3. **FieldEncryptionTest.java** - Test JPA converter
4. **test_encryption.py** - Python encryption tests

## Verification

1. Run tests: `./gradlew test` and `pytest`
2. Verify data is encrypted in database
3. Test key rotation process
4. Verify encryption with different contexts
5. Test envelope encryption with KMS
