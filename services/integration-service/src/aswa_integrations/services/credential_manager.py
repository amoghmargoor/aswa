import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import redis.asyncio as redis
import structlog

from aswa_integrations.config import get_settings

logger = structlog.get_logger()


class CredentialManager:
    """Manages encrypted storage of integration credentials."""

    def __init__(self):
        self.settings = get_settings()
        self._fernet: Fernet | None = None
        self._redis: redis.Redis | None = None

    async def initialize(self) -> None:
        """Initialize the credential manager."""
        # Derive encryption key
        key = self._derive_key(self.settings.encryption_key)
        self._fernet = Fernet(key)

        # Connect to Redis
        self._redis = redis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        logger.info("Credential manager initialized")

    async def close(self) -> None:
        """Close connections."""
        if self._redis:
            await self._redis.close()

    def _derive_key(self, password: str) -> bytes:
        """Derive a Fernet key from a password."""
        salt = b"aswa-integrations-salt"  # In production, use a random salt per credential
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    async def store_credentials(
        self,
        credential_id: str,
        credentials: dict[str, str],
        ttl: int | None = None,
    ) -> None:
        """Store encrypted credentials.

        Args:
            credential_id: Unique identifier for the credentials
            credentials: Dictionary of credential key-value pairs
            ttl: Optional TTL in seconds
        """
        if not self._fernet or not self._redis:
            raise RuntimeError("Credential manager not initialized")

        # Encrypt credentials
        json_data = json.dumps(credentials)
        encrypted = self._fernet.encrypt(json_data.encode())

        # Store in Redis
        key = f"credentials:{credential_id}"
        if ttl:
            await self._redis.setex(key, ttl, encrypted.decode())
        else:
            await self._redis.set(key, encrypted.decode())

        logger.info("Credentials stored", credential_id=credential_id)

    async def get_credentials(self, credential_id: str) -> dict[str, str] | None:
        """Retrieve decrypted credentials.

        Args:
            credential_id: Unique identifier for the credentials

        Returns:
            Decrypted credentials or None if not found
        """
        if not self._fernet or not self._redis:
            raise RuntimeError("Credential manager not initialized")

        key = f"credentials:{credential_id}"
        encrypted = await self._redis.get(key)

        if not encrypted:
            return None

        # Decrypt credentials
        decrypted = self._fernet.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())

    async def delete_credentials(self, credential_id: str) -> bool:
        """Delete stored credentials.

        Args:
            credential_id: Unique identifier for the credentials

        Returns:
            True if deleted, False if not found
        """
        if not self._redis:
            raise RuntimeError("Credential manager not initialized")

        key = f"credentials:{credential_id}"
        result = await self._redis.delete(key)
        return result > 0

    async def rotate_credentials(
        self,
        credential_id: str,
        new_credentials: dict[str, str],
    ) -> None:
        """Rotate credentials atomically.

        Args:
            credential_id: Unique identifier for the credentials
            new_credentials: New credential values
        """
        # Store new credentials with temporary ID
        temp_id = f"{credential_id}:new"
        await self.store_credentials(temp_id, new_credentials)

        # Atomically swap
        await self._redis.rename(f"credentials:{temp_id}", f"credentials:{credential_id}")

        logger.info("Credentials rotated", credential_id=credential_id)
