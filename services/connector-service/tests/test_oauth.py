"""Tests for OAuth framework."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from aswa_connector.framework.oauth.models import OAuthProvider, OAuthTokens
from aswa_connector.framework.oauth.token_store import TokenStore
from aswa_connector.framework.oauth.manager import OAuthManager


class TestTokenStore:
    """Tests for token encryption and storage."""

    @pytest.fixture
    def token_store(self) -> TokenStore:
        """Create token store."""
        return TokenStore(encryption_key="test-key-for-encryption-32bytes!")

    def test_encrypt_decrypt_tokens(self, token_store: TokenStore) -> None:
        """Test token encryption and decryption."""
        tenant_id = uuid4()
        tokens = OAuthTokens(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
        )

        encrypted = token_store.encrypt_tokens(tokens, tenant_id)
        assert encrypted != tokens.access_token

        decrypted = token_store.decrypt_tokens(encrypted, tenant_id)
        assert decrypted.access_token == tokens.access_token
        assert decrypted.refresh_token == tokens.refresh_token

    def test_different_tenants_different_keys(self, token_store: TokenStore) -> None:
        """Test that different tenants use different encryption keys."""
        tokens = OAuthTokens(access_token="test-token")
        tenant1 = uuid4()
        tenant2 = uuid4()

        encrypted1 = token_store.encrypt_tokens(tokens, tenant1)
        encrypted2 = token_store.encrypt_tokens(tokens, tenant2)

        assert encrypted1 != encrypted2

    def test_decrypt_wrong_tenant_fails(self, token_store: TokenStore) -> None:
        """Test that decryption with wrong tenant fails."""
        tokens = OAuthTokens(access_token="test-token")
        tenant1 = uuid4()
        tenant2 = uuid4()

        encrypted = token_store.encrypt_tokens(tokens, tenant1)

        with pytest.raises(ValueError):
            token_store.decrypt_tokens(encrypted, tenant2)


class TestOAuthManager:
    """Tests for OAuth flow manager."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create mock Redis."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def oauth_manager(self, mock_redis: AsyncMock) -> OAuthManager:
        """Create OAuth manager."""
        return OAuthManager(redis=mock_redis)

    def test_get_provider_for_connector(self, oauth_manager: OAuthManager) -> None:
        """Test getting OAuth provider for connector type."""
        assert oauth_manager.get_provider_for_connector("gmail") == OAuthProvider.GOOGLE
        assert oauth_manager.get_provider_for_connector("google_drive") == OAuthProvider.GOOGLE
        assert oauth_manager.get_provider_for_connector("slack") == OAuthProvider.SLACK
        assert oauth_manager.get_provider_for_connector("salesforce") == OAuthProvider.SALESFORCE

    def test_get_provider_unknown_connector(self, oauth_manager: OAuthManager) -> None:
        """Test getting provider for unknown connector raises."""
        with pytest.raises(ValueError):
            oauth_manager.get_provider_for_connector("unknown")

    @pytest.mark.asyncio
    async def test_get_authorization_url(
        self, oauth_manager: OAuthManager, mock_redis: AsyncMock
    ) -> None:
        """Test generating authorization URL."""
        auth_url = await oauth_manager.get_authorization_url(
            provider=OAuthProvider.GOOGLE,
            tenant_id=uuid4(),
            connector_type="gmail",
        )

        assert auth_url.url.startswith("https://accounts.google.com")
        assert auth_url.state
        assert auth_url.provider == OAuthProvider.GOOGLE

        # Verify state was stored
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(
        self, oauth_manager: OAuthManager, mock_redis: AsyncMock
    ) -> None:
        """Test code exchange with invalid state."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await oauth_manager.exchange_code(
            provider=OAuthProvider.GOOGLE,
            code="test-code",
            state="invalid-state",
        )

        assert result.success is False
        assert result.error == "invalid_state"
