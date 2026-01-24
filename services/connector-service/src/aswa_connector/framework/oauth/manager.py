"""OAuth flow manager."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from redis.asyncio import Redis

from aswa_common.logging import get_logger

from aswa_connector.config import settings
from aswa_connector.framework.oauth.models import (
    OAuthProvider,
    OAuthState,
    OAuthTokens,
    OAuthAuthorizationUrl,
    OAuthCallbackResult,
)

logger = get_logger(__name__)


# OAuth provider configurations
OAUTH_PROVIDERS: dict[OAuthProvider, dict[str, Any]] = {
    OAuthProvider.GOOGLE: {
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": {
            "gmail": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.metadata",
            ],
            "google_drive": [
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/drive.metadata.readonly",
            ],
        },
        "extra_params": {
            "access_type": "offline",
            "prompt": "consent",
        },
    },
    OAuthProvider.SLACK: {
        "authorization_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": {
            "slack": [
                "channels:history",
                "channels:read",
                "files:read",
                "groups:history",
                "groups:read",
                "im:history",
                "im:read",
                "mpim:history",
                "mpim:read",
                "users:read",
            ],
        },
        "extra_params": {},
    },
    OAuthProvider.SALESFORCE: {
        "authorization_url": "https://{domain}/services/oauth2/authorize",
        "token_url": "https://{domain}/services/oauth2/token",
        "scopes": {
            "salesforce": [
                "api",
                "refresh_token",
                "offline_access",
            ],
        },
        "extra_params": {},
    },
    OAuthProvider.MICROSOFT: {
        "authorization_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": {
            "sharepoint": [
                "Files.Read.All",
                "Sites.Read.All",
                "offline_access",
            ],
        },
        "extra_params": {},
    },
}


class OAuthManager:
    """Manages OAuth flows for all providers."""

    STATE_TTL = 600  # 10 minutes

    def __init__(self, redis: Redis):
        """Initialize OAuth manager.

        Args:
            redis: Redis client for state storage
        """
        self.redis = redis
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_client_credentials(
        self,
        provider: OAuthProvider,
    ) -> tuple[str, str]:
        """Get client ID and secret for a provider.

        Args:
            provider: OAuth provider

        Returns:
            Tuple of (client_id, client_secret)
        """
        if provider == OAuthProvider.GOOGLE:
            return settings.oauth.google_client_id, settings.oauth.google_client_secret
        elif provider == OAuthProvider.SLACK:
            return settings.oauth.slack_client_id, settings.oauth.slack_client_secret
        elif provider == OAuthProvider.SALESFORCE:
            return (
                settings.oauth.salesforce_client_id,
                settings.oauth.salesforce_client_secret,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def get_authorization_url(
        self,
        provider: OAuthProvider,
        tenant_id: UUID,
        connector_type: str,
        user_id: UUID | None = None,
        connection_id: UUID | None = None,
        extra_scopes: list[str] | None = None,
    ) -> OAuthAuthorizationUrl:
        """Generate OAuth authorization URL.

        Args:
            provider: OAuth provider
            tenant_id: Tenant identifier
            connector_type: Type of connector (gmail, slack, etc.)
            user_id: Optional user identifier
            connection_id: Optional connection ID for re-auth
            extra_scopes: Additional scopes to request

        Returns:
            Authorization URL and state
        """
        provider_config = OAUTH_PROVIDERS.get(provider)
        if not provider_config:
            raise ValueError(f"Unknown provider: {provider}")

        # Get scopes for connector type
        scopes = provider_config["scopes"].get(connector_type, [])
        if extra_scopes:
            scopes = list(set(scopes + extra_scopes))

        # Generate state
        state_id = secrets.token_urlsafe(32)
        redirect_uri = f"{settings.oauth.redirect_base_url}/api/v1/oauth/{provider.value}/callback"

        state = OAuthState(
            state_id=state_id,
            provider=provider,
            tenant_id=tenant_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            connector_type=connector_type,
            connection_id=connection_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.STATE_TTL),
        )

        # Store state in Redis
        await self.redis.set(
            f"oauth:state:{state_id}",
            state.model_dump_json(),
            ex=self.STATE_TTL,
        )

        # Build authorization URL
        client_id, _ = self._get_client_credentials(provider)

        auth_url = provider_config["authorization_url"]
        if provider == OAuthProvider.SALESFORCE:
            auth_url = auth_url.format(domain=settings.oauth.salesforce_domain)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state_id,
            **provider_config.get("extra_params", {}),
        }

        # Build URL with params
        url_parts = [f"{k}={v}" for k, v in params.items()]
        full_url = f"{auth_url}?{'&'.join(url_parts)}"

        logger.info(f"Generated OAuth URL for {provider.value}/{connector_type}")

        return OAuthAuthorizationUrl(
            url=full_url,
            state=state_id,
            provider=provider,
        )

    async def exchange_code(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
    ) -> OAuthCallbackResult:
        """Exchange authorization code for tokens.

        Args:
            provider: OAuth provider
            code: Authorization code
            state: State parameter

        Returns:
            Callback result with tokens or error
        """
        # Retrieve and validate state
        state_data = await self.redis.get(f"oauth:state:{state}")
        if not state_data:
            return OAuthCallbackResult(
                success=False,
                error="invalid_state",
                error_description="State expired or invalid",
            )

        oauth_state = OAuthState.model_validate_json(state_data)

        # Delete state (one-time use)
        await self.redis.delete(f"oauth:state:{state}")

        # Get provider config
        provider_config = OAUTH_PROVIDERS.get(provider)
        if not provider_config:
            return OAuthCallbackResult(
                success=False,
                error="invalid_provider",
                error_description=f"Unknown provider: {provider}",
            )

        # Get credentials
        client_id, client_secret = self._get_client_credentials(provider)

        # Build token URL
        token_url = provider_config["token_url"]
        if provider == OAuthProvider.SALESFORCE:
            token_url = token_url.format(domain=settings.oauth.salesforce_domain)

        # Exchange code for tokens
        http_client = await self._get_http_client()

        try:
            response = await http_client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": oauth_state.redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"Token exchange failed: {response.status_code} - {error_data}")
                return OAuthCallbackResult(
                    success=False,
                    error=error_data.get("error", "token_exchange_failed"),
                    error_description=error_data.get(
                        "error_description", "Failed to exchange code"
                    ),
                )

            token_data = response.json()

            # Parse tokens
            expires_in = token_data.get("expires_in")
            expires_at = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            tokens = OAuthTokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=expires_at,
                expires_in=expires_in,
                scope=token_data.get("scope"),
                id_token=token_data.get("id_token"),
                extra={
                    k: v
                    for k, v in token_data.items()
                    if k
                    not in [
                        "access_token",
                        "refresh_token",
                        "token_type",
                        "expires_in",
                        "scope",
                        "id_token",
                    ]
                },
            )

            logger.info(f"OAuth token exchange successful for {provider.value}")

            return OAuthCallbackResult(
                success=True,
                tokens=tokens,
                tenant_id=oauth_state.tenant_id,
                connection_id=oauth_state.connection_id,
                connector_type=oauth_state.connector_type,
            )

        except Exception as e:
            logger.exception(f"Token exchange error: {e}")
            return OAuthCallbackResult(
                success=False,
                error="token_exchange_error",
                error_description=str(e),
            )

    async def refresh_token(
        self,
        provider: OAuthProvider,
        refresh_token: str,
    ) -> OAuthTokens | None:
        """Refresh an access token.

        Args:
            provider: OAuth provider
            refresh_token: Refresh token

        Returns:
            New tokens or None if refresh fails
        """
        provider_config = OAUTH_PROVIDERS.get(provider)
        if not provider_config:
            logger.error(f"Unknown provider: {provider}")
            return None

        client_id, client_secret = self._get_client_credentials(provider)

        token_url = provider_config["token_url"]
        if provider == OAuthProvider.SALESFORCE:
            token_url = token_url.format(domain=settings.oauth.salesforce_domain)

        http_client = await self._get_http_client()

        try:
            response = await http_client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.status_code}")
                return None

            token_data = response.json()

            expires_in = token_data.get("expires_in")
            expires_at = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return OAuthTokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", refresh_token),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=expires_at,
                expires_in=expires_in,
                scope=token_data.get("scope"),
            )

        except Exception as e:
            logger.exception(f"Token refresh error: {e}")
            return None

    def get_provider_for_connector(self, connector_type: str) -> OAuthProvider:
        """Get OAuth provider for a connector type.

        Args:
            connector_type: Connector type (gmail, slack, etc.)

        Returns:
            OAuth provider
        """
        mapping = {
            "gmail": OAuthProvider.GOOGLE,
            "google_drive": OAuthProvider.GOOGLE,
            "slack": OAuthProvider.SLACK,
            "salesforce": OAuthProvider.SALESFORCE,
            "sharepoint": OAuthProvider.MICROSOFT,
        }

        provider = mapping.get(connector_type)
        if not provider:
            raise ValueError(f"No OAuth provider for connector: {connector_type}")

        return provider
