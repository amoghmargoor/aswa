import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode
import httpx
from pydantic import BaseModel
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.services.credential_manager import CredentialManager

logger = structlog.get_logger()


class JiraOAuthConfig(BaseModel):
    """Jira OAuth configuration."""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = [
        "read:jira-work",
        "write:jira-work",
        "read:jira-user",
        "offline_access",
    ]


class JiraTokens(BaseModel):
    """Jira OAuth tokens."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str
    cloud_id: str | None = None


class JiraOAuthHandler:
    """Handles Jira OAuth 2.0 flow."""

    AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
    TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

    def __init__(
        self,
        config: JiraOAuthConfig,
        credential_manager: CredentialManager,
    ):
        """Initialize OAuth handler.

        Args:
            config: OAuth configuration
            credential_manager: Credential storage manager
        """
        self.config = config
        self.credential_manager = credential_manager
        self._states: dict[str, dict] = {}  # In production, use Redis

    def get_authorization_url(
        self,
        tenant_id: str,
        callback_url: str | None = None,
    ) -> tuple[str, str]:
        """Generate OAuth authorization URL.

        Args:
            tenant_id: ASWA tenant identifier
            callback_url: Optional custom callback URL

        Returns:
            Tuple of (authorization URL, state)
        """
        state = secrets.token_urlsafe(32)

        # Store state for validation
        self._states[state] = {
            "tenant_id": tenant_id,
            "created_at": datetime.utcnow(),
        }

        params = {
            "audience": "api.atlassian.com",
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
            "redirect_uri": callback_url or self.config.redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }

        url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"

        logger.info(
            "Generated Jira authorization URL",
            tenant_id=tenant_id,
        )

        return url, state

    async def exchange_code(
        self,
        code: str,
        state: str,
    ) -> JiraTokens:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code
            state: State parameter for validation

        Returns:
            OAuth tokens

        Raises:
            ValueError if state is invalid
        """
        # Validate state
        state_data = self._states.pop(state, None)
        if not state_data:
            raise ValueError("Invalid or expired state")

        # Check state age (10 minute timeout)
        if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=10):
            raise ValueError("State expired")

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "code": code,
                    "redirect_uri": self.config.redirect_uri,
                },
            )

            if not response.is_success:
                logger.error(
                    "Token exchange failed",
                    status=response.status_code,
                    error=response.text,
                )
                raise ValueError(f"Token exchange failed: {response.text}")

            data = response.json()

        # Get accessible resources (cloud ID)
        cloud_id = await self._get_cloud_id(data["access_token"])

        tokens = JiraTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.utcnow() + timedelta(seconds=data["expires_in"]),
            scope=data.get("scope", ""),
            cloud_id=cloud_id,
        )

        # Store tokens
        tenant_id = state_data["tenant_id"]
        await self._store_tokens(tenant_id, tokens)

        logger.info(
            "Jira OAuth tokens exchanged",
            tenant_id=tenant_id,
            cloud_id=cloud_id,
        )

        return tokens

    async def refresh_tokens(
        self,
        tenant_id: str,
    ) -> JiraTokens | None:
        """Refresh access token.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            New tokens or None if refresh failed
        """
        # Get current tokens
        current = await self._get_tokens(tenant_id)
        if not current:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": current.refresh_token,
                },
            )

            if not response.is_success:
                logger.error(
                    "Token refresh failed",
                    tenant_id=tenant_id,
                    status=response.status_code,
                )
                return None

            data = response.json()

        tokens = JiraTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", current.refresh_token),
            expires_at=datetime.utcnow() + timedelta(seconds=data["expires_in"]),
            scope=data.get("scope", current.scope),
            cloud_id=current.cloud_id,
        )

        await self._store_tokens(tenant_id, tokens)

        logger.info("Jira tokens refreshed", tenant_id=tenant_id)

        return tokens

    async def get_valid_tokens(
        self,
        tenant_id: str,
    ) -> JiraTokens | None:
        """Get valid tokens, refreshing if necessary.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            Valid tokens or None
        """
        tokens = await self._get_tokens(tenant_id)
        if not tokens:
            return None

        # Refresh if expiring soon (within 5 minutes)
        if tokens.expires_at <= datetime.utcnow() + timedelta(minutes=5):
            tokens = await self.refresh_tokens(tenant_id)

        return tokens

    async def revoke_tokens(
        self,
        tenant_id: str,
    ) -> bool:
        """Revoke OAuth tokens.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            True if revoked
        """
        credential_id = f"jira:tokens:{tenant_id}"
        result = await self.credential_manager.delete_credentials(credential_id)

        if result:
            logger.info("Jira tokens revoked", tenant_id=tenant_id)

        return result

    async def _get_cloud_id(self, access_token: str) -> str | None:
        """Get Jira Cloud ID for the authorized user.

        Args:
            access_token: OAuth access token

        Returns:
            Cloud ID or None
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.ACCESSIBLE_RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.is_success:
                resources = response.json()
                if resources:
                    return resources[0]["id"]

        return None

    async def _store_tokens(
        self,
        tenant_id: str,
        tokens: JiraTokens,
    ) -> None:
        """Store tokens securely.

        Args:
            tenant_id: ASWA tenant identifier
            tokens: OAuth tokens
        """
        credential_id = f"jira:tokens:{tenant_id}"
        await self.credential_manager.store_credentials(
            credential_id,
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": tokens.expires_at.isoformat(),
                "scope": tokens.scope,
                "cloud_id": tokens.cloud_id or "",
            },
        )

    async def _get_tokens(
        self,
        tenant_id: str,
    ) -> JiraTokens | None:
        """Retrieve stored tokens.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            Tokens or None
        """
        credential_id = f"jira:tokens:{tenant_id}"
        data = await self.credential_manager.get_credentials(credential_id)

        if not data:
            return None

        return JiraTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            scope=data["scope"],
            cloud_id=data.get("cloud_id"),
        )
