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
