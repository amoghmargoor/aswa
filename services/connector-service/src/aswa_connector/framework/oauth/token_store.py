"""Encrypted token storage."""

import base64
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

from aswa_connector.config import settings
from aswa_connector.framework.oauth.models import OAuthTokens

logger = get_logger(__name__)


class TokenStore:
    """Encrypted storage for OAuth tokens.

    Uses Fernet symmetric encryption to protect tokens at rest.
    Each tenant's tokens are encrypted with a key derived from
    the master key and tenant ID.
    """

    def __init__(self, encryption_key: str | None = None):
        """Initialize token store.

        Args:
            encryption_key: 32-byte encryption key. Uses settings if not provided.
        """
        key = encryption_key or settings.oauth.encryption_key
        # Ensure key is 32 bytes for Fernet
        self._master_key = key.encode()[:32].ljust(32, b"0")

    def _get_tenant_cipher(self, tenant_id: UUID) -> Fernet:
        """Get cipher for a specific tenant.

        Derives a unique key for each tenant from the master key.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Fernet cipher for the tenant
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=str(tenant_id).encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._master_key))
        return Fernet(key)

    def encrypt_tokens(self, tokens: OAuthTokens, tenant_id: UUID) -> str:
        """Encrypt tokens for storage.

        Args:
            tokens: OAuth tokens to encrypt
            tenant_id: Tenant identifier

        Returns:
            Encrypted token string
        """
        cipher = self._get_tenant_cipher(tenant_id)
        token_data = tokens.model_dump_json()
        encrypted = cipher.encrypt(token_data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_tokens(self, encrypted: str, tenant_id: UUID) -> OAuthTokens:
        """Decrypt stored tokens.

        Args:
            encrypted: Encrypted token string
            tenant_id: Tenant identifier

        Returns:
            Decrypted OAuth tokens

        Raises:
            ValueError: If decryption fails
        """
        try:
            cipher = self._get_tenant_cipher(tenant_id)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
            decrypted = cipher.decrypt(encrypted_bytes)
            return OAuthTokens.model_validate_json(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt tokens: {e}")
            raise ValueError("Failed to decrypt tokens") from e

    async def store_tokens(
        self,
        db: AsyncSession,
        connection_id: UUID,
        tenant_id: UUID,
        tokens: OAuthTokens,
    ) -> None:
        """Store encrypted tokens in database.

        Args:
            db: Database session
            connection_id: Connection identifier
            tenant_id: Tenant identifier
            tokens: OAuth tokens to store
        """
        from aswa_connector.models.oauth_token import OAuthTokenModel

        encrypted = self.encrypt_tokens(tokens, tenant_id)

        # Check if token record exists
        stmt = select(OAuthTokenModel).where(
            OAuthTokenModel.connection_id == connection_id,
            OAuthTokenModel.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_tokens = encrypted
            existing.expires_at = tokens.expires_at
            existing.updated_at = datetime.now(timezone.utc)
        else:
            token_record = OAuthTokenModel(
                connection_id=connection_id,
                tenant_id=tenant_id,
                encrypted_tokens=encrypted,
                expires_at=tokens.expires_at,
            )
            db.add(token_record)

        await db.flush()
        logger.debug(f"Stored tokens for connection {connection_id}")

    async def get_tokens(
        self,
        db: AsyncSession,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> OAuthTokens | None:
        """Retrieve and decrypt tokens from database.

        Args:
            db: Database session
            connection_id: Connection identifier
            tenant_id: Tenant identifier

        Returns:
            Decrypted tokens or None if not found
        """
        from aswa_connector.models.oauth_token import OAuthTokenModel

        stmt = select(OAuthTokenModel).where(
            OAuthTokenModel.connection_id == connection_id,
            OAuthTokenModel.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if token_record is None:
            return None

        return self.decrypt_tokens(token_record.encrypted_tokens, tenant_id)

    async def delete_tokens(
        self,
        db: AsyncSession,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Delete tokens from database.

        Args:
            db: Database session
            connection_id: Connection identifier
            tenant_id: Tenant identifier
        """
        from sqlalchemy import delete
        from aswa_connector.models.oauth_token import OAuthTokenModel

        stmt = delete(OAuthTokenModel).where(
            OAuthTokenModel.connection_id == connection_id,
            OAuthTokenModel.tenant_id == tenant_id,
        )
        await db.execute(stmt)
        logger.debug(f"Deleted tokens for connection {connection_id}")
