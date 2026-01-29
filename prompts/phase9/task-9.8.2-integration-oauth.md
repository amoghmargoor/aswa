# Task 9.8.2: Integration OAuth

## Objective

Implement OAuth 2.0 integration for third-party services, enabling agents to securely connect to external APIs like Slack, Google, Microsoft, and GitHub.

## Prerequisites

- Task 9.8.1 completed (Trigger Connectors)
- Secure credential storage
- Encryption infrastructure

## Implementation

### Step 1: OAuth Models

```python
# services/agent-service/src/aswa_agents/integrations/oauth/models.py
"""OAuth integration models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from aswa_agents.db.base import Base


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    SLACK = "slack"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"
    JIRA = "jira"
    LINEAR = "linear"
    ZENDESK = "zendesk"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    CUSTOM = "custom"


class OAuthGrantType(str, Enum):
    """OAuth grant types."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"


class OAuthConnectionStatus(str, Enum):
    """Connection status."""

    PENDING = "pending"
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class OAuthProviderConfigModel(Base):
    """SQLAlchemy model for OAuth provider configurations."""

    __tablename__ = "oauth_provider_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Provider info
    provider = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # OAuth settings
    client_id = Column(String(500), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)  # Encrypted
    authorization_url = Column(String(500), nullable=False)
    token_url = Column(String(500), nullable=False)
    scopes = Column(JSON, default=list)
    redirect_uri = Column(String(500), nullable=True)

    # Additional settings
    additional_params = Column(JSON, default=dict)  # Extra OAuth params

    # Status
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_oauth_provider_configs_tenant", "tenant_id"),
        Index("idx_oauth_provider_configs_provider", "provider"),
    )


class OAuthConnectionModel(Base):
    """SQLAlchemy model for OAuth connections."""

    __tablename__ = "oauth_connections"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Connection owner
    user_id = Column(String(100), nullable=True)  # User who authorized
    agent_id = Column(PGUUID(as_uuid=True), nullable=True)  # Or agent-level

    # Provider info
    provider = Column(String(50), nullable=False)
    provider_config_id = Column(PGUUID(as_uuid=True), nullable=True)

    # Tokens (encrypted)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")

    # Token metadata
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(JSON, default=list)

    # Provider-specific data
    provider_user_id = Column(String(200), nullable=True)
    provider_user_name = Column(String(200), nullable=True)
    provider_data = Column(JSON, default=dict)

    # Status
    status = Column(String(50), default=OAuthConnectionStatus.PENDING.value)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_oauth_connections_tenant", "tenant_id"),
        Index("idx_oauth_connections_user", "user_id"),
        Index("idx_oauth_connections_agent", "agent_id"),
        Index("idx_oauth_connections_provider", "provider"),
        Index("idx_oauth_connections_status", "status"),
    )


# Pydantic models
class OAuthProviderConfig(BaseModel):
    """OAuth provider configuration."""

    provider: OAuthProvider
    name: str
    description: str | None = None
    client_id: str
    client_secret: str
    authorization_url: str | None = None  # Use default for known providers
    token_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    redirect_uri: str | None = None
    additional_params: dict[str, str] = Field(default_factory=dict)


class OAuthConnection(BaseModel):
    """OAuth connection response."""

    id: UUID
    provider: str
    status: str
    provider_user_id: str | None
    provider_user_name: str | None
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None


class OAuthAuthorizationRequest(BaseModel):
    """Request to start OAuth authorization."""

    provider: OAuthProvider
    scopes: list[str] | None = None
    agent_id: UUID | None = None
    redirect_uri: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class OAuthCallbackData(BaseModel):
    """Data from OAuth callback."""

    code: str
    state: str
    error: str | None = None
    error_description: str | None = None


class TokenResponse(BaseModel):
    """Token response from OAuth provider."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
```

### Step 2: OAuth Provider Definitions

```python
# services/agent-service/src/aswa_agents/integrations/oauth/providers.py
"""OAuth provider definitions."""

from dataclasses import dataclass
from typing import Any

from aswa_agents.integrations.oauth.models import OAuthProvider


@dataclass
class ProviderDefinition:
    """Definition for an OAuth provider."""

    provider: OAuthProvider
    name: str
    authorization_url: str
    token_url: str
    default_scopes: list[str]
    user_info_url: str | None = None
    revoke_url: str | None = None
    supports_refresh: bool = True
    additional_params: dict[str, str] | None = None


PROVIDER_DEFINITIONS: dict[OAuthProvider, ProviderDefinition] = {
    OAuthProvider.SLACK: ProviderDefinition(
        provider=OAuthProvider.SLACK,
        name="Slack",
        authorization_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        default_scopes=[
            "channels:read",
            "chat:write",
            "users:read",
            "app_mentions:read",
        ],
        user_info_url="https://slack.com/api/auth.test",
        revoke_url="https://slack.com/api/auth.revoke",
    ),
    OAuthProvider.GOOGLE: ProviderDefinition(
        provider=OAuthProvider.GOOGLE,
        name="Google",
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        default_scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "openid",
            "email",
            "profile",
        ],
        user_info_url="https://www.googleapis.com/oauth2/v2/userinfo",
        revoke_url="https://oauth2.googleapis.com/revoke",
        additional_params={"access_type": "offline", "prompt": "consent"},
    ),
    OAuthProvider.MICROSOFT: ProviderDefinition(
        provider=OAuthProvider.MICROSOFT,
        name="Microsoft",
        authorization_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        default_scopes=[
            "offline_access",
            "User.Read",
            "Mail.Read",
            "Calendar.Read",
        ],
        user_info_url="https://graph.microsoft.com/v1.0/me",
    ),
    OAuthProvider.GITHUB: ProviderDefinition(
        provider=OAuthProvider.GITHUB,
        name="GitHub",
        authorization_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        default_scopes=["read:user", "repo"],
        user_info_url="https://api.github.com/user",
        supports_refresh=False,
    ),
    OAuthProvider.JIRA: ProviderDefinition(
        provider=OAuthProvider.JIRA,
        name="Jira",
        authorization_url="https://auth.atlassian.com/authorize",
        token_url="https://auth.atlassian.com/oauth/token",
        default_scopes=[
            "read:jira-user",
            "read:jira-work",
            "write:jira-work",
            "offline_access",
        ],
        user_info_url="https://api.atlassian.com/me",
        additional_params={"audience": "api.atlassian.com"},
    ),
    OAuthProvider.LINEAR: ProviderDefinition(
        provider=OAuthProvider.LINEAR,
        name="Linear",
        authorization_url="https://linear.app/oauth/authorize",
        token_url="https://api.linear.app/oauth/token",
        default_scopes=["read", "write"],
    ),
    OAuthProvider.ZENDESK: ProviderDefinition(
        provider=OAuthProvider.ZENDESK,
        name="Zendesk",
        authorization_url="https://{subdomain}.zendesk.com/oauth/authorizations/new",
        token_url="https://{subdomain}.zendesk.com/oauth/tokens",
        default_scopes=["read", "write"],
    ),
    OAuthProvider.SALESFORCE: ProviderDefinition(
        provider=OAuthProvider.SALESFORCE,
        name="Salesforce",
        authorization_url="https://login.salesforce.com/services/oauth2/authorize",
        token_url="https://login.salesforce.com/services/oauth2/token",
        default_scopes=["api", "refresh_token"],
        user_info_url="https://login.salesforce.com/services/oauth2/userinfo",
    ),
    OAuthProvider.HUBSPOT: ProviderDefinition(
        provider=OAuthProvider.HUBSPOT,
        name="HubSpot",
        authorization_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        default_scopes=["crm.objects.contacts.read", "crm.objects.contacts.write"],
    ),
}


def get_provider_definition(provider: OAuthProvider) -> ProviderDefinition | None:
    """Get provider definition."""
    return PROVIDER_DEFINITIONS.get(provider)


def get_all_providers() -> list[dict[str, Any]]:
    """Get all provider definitions for display."""
    return [
        {
            "provider": p.provider.value,
            "name": p.name,
            "default_scopes": p.default_scopes,
            "supports_refresh": p.supports_refresh,
        }
        for p in PROVIDER_DEFINITIONS.values()
    ]
```

### Step 3: OAuth Service

```python
# services/agent-service/src/aswa_agents/integrations/oauth/service.py
"""OAuth service for managing integrations."""

import base64
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode, parse_qs
from uuid import UUID

import httpx
import structlog

from aswa_agents.integrations.oauth.models import (
    OAuthProvider,
    OAuthProviderConfig,
    OAuthAuthorizationRequest,
    OAuthCallbackData,
    OAuthConnectionStatus,
    OAuthConnectionModel,
    OAuthProviderConfigModel,
    TokenResponse,
)
from aswa_agents.integrations.oauth.providers import (
    get_provider_definition,
    get_all_providers,
)
from aswa_agents.integrations.oauth.repository import OAuthRepository
from aswa_agents.services.encryption_service import EncryptionService

logger = structlog.get_logger()


class OAuthService:
    """
    Service for OAuth integration management.

    Handles authorization flows, token management, and API access.
    """

    def __init__(self):
        self._repo = OAuthRepository()
        self._encryption = EncryptionService()
        self._logger = logger.bind(component="OAuthService")
        self._pending_states: dict[str, dict] = {}  # State -> context mapping

    async def get_available_providers(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Get list of available OAuth providers."""
        all_providers = get_all_providers()

        # Get tenant-specific configurations
        configs = await self._repo.list_provider_configs(tenant_id)
        config_map = {c.provider: c for c in configs}

        for provider in all_providers:
            config = config_map.get(provider["provider"])
            provider["configured"] = config is not None and config.enabled

        return all_providers

    async def configure_provider(
        self,
        tenant_id: str,
        config: OAuthProviderConfig,
    ) -> dict[str, Any]:
        """Configure an OAuth provider."""
        # Get provider definition for defaults
        definition = get_provider_definition(config.provider)

        # Encrypt client secret
        encrypted_secret = self._encryption.encrypt(config.client_secret)

        db_config = await self._repo.create_provider_config(
            tenant_id=tenant_id,
            provider=config.provider.value,
            name=config.name,
            description=config.description,
            client_id=config.client_id,
            client_secret_encrypted=encrypted_secret,
            authorization_url=config.authorization_url or (definition.authorization_url if definition else ""),
            token_url=config.token_url or (definition.token_url if definition else ""),
            scopes=config.scopes or (definition.default_scopes if definition else []),
            redirect_uri=config.redirect_uri,
            additional_params=config.additional_params,
        )

        return {
            "id": str(db_config.id),
            "provider": db_config.provider,
            "name": db_config.name,
            "configured": True,
        }

    async def start_authorization(
        self,
        tenant_id: str,
        user_id: str,
        request: OAuthAuthorizationRequest,
    ) -> dict[str, Any]:
        """Start OAuth authorization flow."""
        # Get provider config
        provider_config = await self._repo.get_provider_config(
            tenant_id, request.provider.value
        )

        if not provider_config:
            # Try using default definition
            definition = get_provider_definition(request.provider)
            if not definition:
                raise ValueError(f"Provider {request.provider.value} not configured")

            raise ValueError(f"Provider {request.provider.value} requires configuration")

        # Generate state
        state = secrets.token_urlsafe(32)

        # Store state context
        self._pending_states[state] = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "provider": request.provider.value,
            "agent_id": str(request.agent_id) if request.agent_id else None,
            "custom_state": request.state,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Build authorization URL
        scopes = request.scopes or provider_config.scopes
        redirect_uri = request.redirect_uri or provider_config.redirect_uri

        params = {
            "client_id": provider_config.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }

        # Add additional params
        if provider_config.additional_params:
            params.update(provider_config.additional_params)

        auth_url = f"{provider_config.authorization_url}?{urlencode(params)}"

        self._logger.info(
            "Authorization started",
            provider=request.provider.value,
            tenant_id=tenant_id,
        )

        return {
            "authorization_url": auth_url,
            "state": state,
            "expires_in": 600,  # 10 minutes
        }

    async def handle_callback(
        self,
        callback: OAuthCallbackData,
    ) -> dict[str, Any]:
        """Handle OAuth callback."""
        # Validate state
        context = self._pending_states.pop(callback.state, None)

        if not context:
            raise ValueError("Invalid or expired state")

        if callback.error:
            self._logger.warning(
                "OAuth callback error",
                error=callback.error,
                description=callback.error_description,
            )
            raise ValueError(callback.error_description or callback.error)

        tenant_id = context["tenant_id"]
        provider = context["provider"]

        # Get provider config
        provider_config = await self._repo.get_provider_config(tenant_id, provider)

        if not provider_config:
            raise ValueError("Provider configuration not found")

        # Exchange code for tokens
        tokens = await self._exchange_code(
            provider_config=provider_config,
            code=callback.code,
        )

        # Get user info
        user_info = await self._get_user_info(provider, tokens.access_token)

        # Store connection
        connection = await self._repo.create_connection(
            tenant_id=tenant_id,
            user_id=context["user_id"],
            agent_id=context.get("agent_id"),
            provider=provider,
            provider_config_id=provider_config.id,
            access_token_encrypted=self._encryption.encrypt(tokens.access_token),
            refresh_token_encrypted=self._encryption.encrypt(tokens.refresh_token) if tokens.refresh_token else None,
            token_type=tokens.token_type,
            expires_at=datetime.utcnow() + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None,
            scopes=tokens.scope.split(" ") if tokens.scope else provider_config.scopes,
            provider_user_id=user_info.get("id"),
            provider_user_name=user_info.get("name") or user_info.get("email"),
            provider_data=user_info,
        )

        self._logger.info(
            "OAuth connection created",
            connection_id=str(connection.id),
            provider=provider,
        )

        return {
            "connection_id": str(connection.id),
            "provider": provider,
            "provider_user_name": connection.provider_user_name,
            "status": OAuthConnectionStatus.CONNECTED.value,
        }

    async def _exchange_code(
        self,
        provider_config: OAuthProviderConfigModel,
        code: str,
    ) -> TokenResponse:
        """Exchange authorization code for tokens."""
        client_secret = self._encryption.decrypt(provider_config.client_secret_encrypted)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_config.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": provider_config.redirect_uri,
                    "client_id": provider_config.client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                self._logger.error(
                    "Token exchange failed",
                    status=response.status_code,
                    body=response.text,
                )
                raise ValueError("Failed to exchange authorization code")

            data = response.json()

            return TokenResponse(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in"),
                refresh_token=data.get("refresh_token"),
                scope=data.get("scope"),
            )

    async def _get_user_info(
        self,
        provider: str,
        access_token: str,
    ) -> dict[str, Any]:
        """Get user info from provider."""
        definition = get_provider_definition(OAuthProvider(provider))

        if not definition or not definition.user_info_url:
            return {}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                definition.user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                self._logger.warning(
                    "Failed to get user info",
                    provider=provider,
                    status=response.status_code,
                )
                return {}

            return response.json()

    async def refresh_token(
        self,
        connection_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Refresh an OAuth token."""
        connection = await self._repo.get_connection(connection_id, tenant_id)

        if not connection or not connection.refresh_token_encrypted:
            return False

        provider_config = await self._repo.get_provider_config(
            tenant_id, connection.provider
        )

        if not provider_config:
            return False

        refresh_token = self._encryption.decrypt(connection.refresh_token_encrypted)
        client_secret = self._encryption.decrypt(provider_config.client_secret_encrypted)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider_config.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": provider_config.client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                self._logger.error(
                    "Token refresh failed",
                    connection_id=str(connection_id),
                )
                await self._repo.update_connection_status(
                    connection_id, OAuthConnectionStatus.ERROR.value,
                    error="Token refresh failed"
                )
                return False

            data = response.json()

            await self._repo.update_connection_tokens(
                connection_id=connection_id,
                access_token_encrypted=self._encryption.encrypt(data["access_token"]),
                refresh_token_encrypted=self._encryption.encrypt(data.get("refresh_token", refresh_token)),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
            )

            return True

    async def get_access_token(
        self,
        connection_id: UUID,
        tenant_id: str,
    ) -> str | None:
        """Get a valid access token, refreshing if needed."""
        connection = await self._repo.get_connection(connection_id, tenant_id)

        if not connection:
            return None

        # Check if token is expired
        if connection.expires_at and connection.expires_at <= datetime.utcnow():
            if connection.refresh_token_encrypted:
                success = await self.refresh_token(connection_id, tenant_id)
                if not success:
                    return None
                # Reload connection after refresh
                connection = await self._repo.get_connection(connection_id, tenant_id)
            else:
                return None

        # Update last used
        await self._repo.update_connection_last_used(connection_id)

        return self._encryption.decrypt(connection.access_token_encrypted)

    async def list_connections(
        self,
        tenant_id: str,
        user_id: str | None = None,
        agent_id: UUID | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """List OAuth connections."""
        connections = await self._repo.list_connections(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=str(agent_id) if agent_id else None,
            provider=provider,
        )

        return [
            {
                "id": str(c.id),
                "provider": c.provider,
                "status": c.status,
                "provider_user_id": c.provider_user_id,
                "provider_user_name": c.provider_user_name,
                "scopes": c.scopes,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "created_at": c.created_at.isoformat(),
                "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
            }
            for c in connections
        ]

    async def revoke_connection(
        self,
        connection_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Revoke an OAuth connection."""
        connection = await self._repo.get_connection(connection_id, tenant_id)

        if not connection:
            return False

        # Try to revoke at provider
        definition = get_provider_definition(OAuthProvider(connection.provider))

        if definition and definition.revoke_url:
            try:
                access_token = self._encryption.decrypt(connection.access_token_encrypted)

                async with httpx.AsyncClient() as client:
                    await client.post(
                        definition.revoke_url,
                        data={"token": access_token},
                    )
            except Exception as e:
                self._logger.warning(
                    "Failed to revoke at provider",
                    error=str(e),
                )

        # Update status
        await self._repo.update_connection_status(
            connection_id, OAuthConnectionStatus.REVOKED.value
        )

        return True
```

### Step 4: OAuth Repository

```python
# services/agent-service/src/aswa_agents/integrations/oauth/repository.py
"""Repository for OAuth data."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.integrations.oauth.models import (
    OAuthProviderConfigModel,
    OAuthConnectionModel,
    OAuthConnectionStatus,
)

logger = structlog.get_logger()


class OAuthRepository:
    """Repository for OAuth data management."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="OAuthRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    # Provider configs

    async def create_provider_config(
        self,
        tenant_id: str,
        provider: str,
        name: str,
        client_id: str,
        client_secret_encrypted: str,
        authorization_url: str,
        token_url: str,
        scopes: list[str],
        redirect_uri: str | None = None,
        description: str | None = None,
        additional_params: dict | None = None,
    ) -> OAuthProviderConfigModel:
        """Create or update a provider configuration."""
        session = await self._get_session()

        # Check if exists
        existing = await self.get_provider_config(tenant_id, provider)

        if existing:
            existing.name = name
            existing.description = description
            existing.client_id = client_id
            existing.client_secret_encrypted = client_secret_encrypted
            existing.authorization_url = authorization_url
            existing.token_url = token_url
            existing.scopes = scopes
            existing.redirect_uri = redirect_uri
            existing.additional_params = additional_params or {}
            existing.updated_at = datetime.utcnow()
            await session.commit()
            return existing

        config = OAuthProviderConfigModel(
            tenant_id=tenant_id,
            provider=provider,
            name=name,
            description=description,
            client_id=client_id,
            client_secret_encrypted=client_secret_encrypted,
            authorization_url=authorization_url,
            token_url=token_url,
            scopes=scopes,
            redirect_uri=redirect_uri,
            additional_params=additional_params or {},
        )

        session.add(config)
        await session.commit()
        await session.refresh(config)

        return config

    async def get_provider_config(
        self,
        tenant_id: str,
        provider: str,
    ) -> OAuthProviderConfigModel | None:
        """Get provider configuration."""
        session = await self._get_session()

        result = await session.execute(
            select(OAuthProviderConfigModel).where(
                and_(
                    OAuthProviderConfigModel.tenant_id == tenant_id,
                    OAuthProviderConfigModel.provider == provider,
                    OAuthProviderConfigModel.enabled == True,
                )
            )
        )

        return result.scalar_one_or_none()

    async def list_provider_configs(
        self,
        tenant_id: str,
    ) -> list[OAuthProviderConfigModel]:
        """List all provider configurations."""
        session = await self._get_session()

        result = await session.execute(
            select(OAuthProviderConfigModel).where(
                OAuthProviderConfigModel.tenant_id == tenant_id
            )
        )

        return result.scalars().all()

    # Connections

    async def create_connection(
        self,
        tenant_id: str,
        user_id: str,
        provider: str,
        access_token_encrypted: str,
        agent_id: str | None = None,
        provider_config_id: UUID | None = None,
        refresh_token_encrypted: str | None = None,
        token_type: str = "Bearer",
        expires_at: datetime | None = None,
        scopes: list[str] | None = None,
        provider_user_id: str | None = None,
        provider_user_name: str | None = None,
        provider_data: dict | None = None,
    ) -> OAuthConnectionModel:
        """Create an OAuth connection."""
        session = await self._get_session()

        connection = OAuthConnectionModel(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            provider=provider,
            provider_config_id=provider_config_id,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            token_type=token_type,
            expires_at=expires_at,
            scopes=scopes or [],
            provider_user_id=provider_user_id,
            provider_user_name=provider_user_name,
            provider_data=provider_data or {},
            status=OAuthConnectionStatus.CONNECTED.value,
        )

        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        return connection

    async def get_connection(
        self,
        connection_id: UUID,
        tenant_id: str,
    ) -> OAuthConnectionModel | None:
        """Get a connection by ID."""
        session = await self._get_session()

        result = await session.execute(
            select(OAuthConnectionModel).where(
                and_(
                    OAuthConnectionModel.id == connection_id,
                    OAuthConnectionModel.tenant_id == tenant_id,
                )
            )
        )

        return result.scalar_one_or_none()

    async def list_connections(
        self,
        tenant_id: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        provider: str | None = None,
    ) -> list[OAuthConnectionModel]:
        """List OAuth connections."""
        session = await self._get_session()

        conditions = [
            OAuthConnectionModel.tenant_id == tenant_id,
            OAuthConnectionModel.status != OAuthConnectionStatus.REVOKED.value,
        ]

        if user_id:
            conditions.append(OAuthConnectionModel.user_id == user_id)
        if agent_id:
            conditions.append(OAuthConnectionModel.agent_id == agent_id)
        if provider:
            conditions.append(OAuthConnectionModel.provider == provider)

        result = await session.execute(
            select(OAuthConnectionModel)
            .where(and_(*conditions))
            .order_by(OAuthConnectionModel.created_at.desc())
        )

        return result.scalars().all()

    async def update_connection_tokens(
        self,
        connection_id: UUID,
        access_token_encrypted: str,
        refresh_token_encrypted: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Update connection tokens."""
        session = await self._get_session()

        values = {
            "access_token_encrypted": access_token_encrypted,
            "expires_at": expires_at,
            "updated_at": datetime.utcnow(),
            "status": OAuthConnectionStatus.CONNECTED.value,
        }

        if refresh_token_encrypted:
            values["refresh_token_encrypted"] = refresh_token_encrypted

        await session.execute(
            update(OAuthConnectionModel)
            .where(OAuthConnectionModel.id == connection_id)
            .values(**values)
        )

        await session.commit()

    async def update_connection_status(
        self,
        connection_id: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update connection status."""
        session = await self._get_session()

        await session.execute(
            update(OAuthConnectionModel)
            .where(OAuthConnectionModel.id == connection_id)
            .values(
                status=status,
                error_message=error,
                updated_at=datetime.utcnow(),
            )
        )

        await session.commit()

    async def update_connection_last_used(
        self,
        connection_id: UUID,
    ) -> None:
        """Update last used timestamp."""
        session = await self._get_session()

        await session.execute(
            update(OAuthConnectionModel)
            .where(OAuthConnectionModel.id == connection_id)
            .values(last_used_at=datetime.utcnow())
        )

        await session.commit()
```

### Step 5: OAuth API Endpoints

```python
# services/agent-service/src/aswa_agents/api/oauth.py
"""API endpoints for OAuth integration."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import RedirectResponse

from aswa_agents.integrations.oauth.models import (
    OAuthProvider,
    OAuthProviderConfig,
    OAuthAuthorizationRequest,
    OAuthCallbackData,
)
from aswa_agents.integrations.oauth.service import OAuthService

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """List available OAuth providers."""
    tenant_id = "default-tenant"

    service = OAuthService()
    providers = await service.get_available_providers(tenant_id)

    return {"providers": providers}


@router.post("/providers/configure")
async def configure_provider(config: OAuthProviderConfig) -> dict[str, Any]:
    """Configure an OAuth provider."""
    tenant_id = "default-tenant"

    service = OAuthService()

    try:
        return await service.configure_provider(tenant_id, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/authorize")
async def start_authorization(
    request: OAuthAuthorizationRequest,
) -> dict[str, Any]:
    """Start OAuth authorization flow."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = OAuthService()

    try:
        return await service.start_authorization(tenant_id, user_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Handle OAuth callback."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    service = OAuthService()

    callback_data = OAuthCallbackData(
        code=code or "",
        state=state,
        error=error,
        error_description=error_description,
    )

    try:
        result = await service.handle_callback(callback_data)

        # Redirect to success page
        return RedirectResponse(
            url=f"/integrations/success?connection_id={result['connection_id']}&provider={result['provider']}"
        )
    except ValueError as e:
        # Redirect to error page
        return RedirectResponse(
            url=f"/integrations/error?error={str(e)}"
        )


@router.get("/connections")
async def list_connections(
    provider: str | None = None,
    agent_id: UUID | None = None,
) -> dict[str, Any]:
    """List OAuth connections."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = OAuthService()
    connections = await service.list_connections(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        provider=provider,
    )

    return {"connections": connections}


@router.get("/connections/{connection_id}")
async def get_connection(connection_id: UUID) -> dict[str, Any]:
    """Get a specific connection."""
    tenant_id = "default-tenant"

    service = OAuthService()
    connections = await service.list_connections(tenant_id)

    connection = next(
        (c for c in connections if c["id"] == str(connection_id)),
        None
    )

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return connection


@router.delete("/connections/{connection_id}")
async def revoke_connection(connection_id: UUID) -> dict[str, Any]:
    """Revoke an OAuth connection."""
    tenant_id = "default-tenant"

    service = OAuthService()
    success = await service.revoke_connection(connection_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {"revoked": True}


@router.post("/connections/{connection_id}/refresh")
async def refresh_connection(connection_id: UUID) -> dict[str, Any]:
    """Refresh an OAuth connection's tokens."""
    tenant_id = "default-tenant"

    service = OAuthService()
    success = await service.refresh_token(connection_id, tenant_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to refresh token")

    return {"refreshed": True}
```

## Test Cases

```python
# services/agent-service/tests/unit/test_oauth.py
"""Tests for OAuth integration."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from aswa_agents.integrations.oauth.models import (
    OAuthProvider,
    OAuthProviderConfig,
    OAuthAuthorizationRequest,
    OAuthCallbackData,
    OAuthConnectionStatus,
)
from aswa_agents.integrations.oauth.service import OAuthService
from aswa_agents.integrations.oauth.providers import get_provider_definition


class TestOAuthProviders:
    """Test OAuth provider definitions."""

    def test_get_slack_provider(self):
        """Test getting Slack provider definition."""
        definition = get_provider_definition(OAuthProvider.SLACK)

        assert definition is not None
        assert definition.name == "Slack"
        assert "slack.com" in definition.authorization_url

    def test_get_google_provider(self):
        """Test getting Google provider definition."""
        definition = get_provider_definition(OAuthProvider.GOOGLE)

        assert definition is not None
        assert "accounts.google.com" in definition.authorization_url
        assert definition.supports_refresh is True

    def test_get_github_provider(self):
        """Test getting GitHub provider definition."""
        definition = get_provider_definition(OAuthProvider.GITHUB)

        assert definition is not None
        assert definition.supports_refresh is False


class TestOAuthService:
    """Test OAuthService."""

    @pytest.fixture
    def service(self):
        return OAuthService()

    @pytest.mark.asyncio
    async def test_start_authorization(self, service):
        """Test starting authorization flow."""
        mock_config = MagicMock()
        mock_config.client_id = "test-client"
        mock_config.authorization_url = "https://example.com/oauth/authorize"
        mock_config.scopes = ["read", "write"]
        mock_config.redirect_uri = "https://app.example.com/callback"
        mock_config.additional_params = {}

        with patch.object(service._repo, "get_provider_config") as mock_get:
            mock_get.return_value = mock_config

            request = OAuthAuthorizationRequest(
                provider=OAuthProvider.SLACK,
            )

            result = await service.start_authorization(
                "tenant-1", "user-1", request
            )

            assert "authorization_url" in result
            assert "state" in result
            assert "client_id=test-client" in result["authorization_url"]

    @pytest.mark.asyncio
    async def test_start_authorization_no_config(self, service):
        """Test starting authorization without config."""
        with patch.object(service._repo, "get_provider_config") as mock_get:
            mock_get.return_value = None

            request = OAuthAuthorizationRequest(
                provider=OAuthProvider.CUSTOM,
            )

            with pytest.raises(ValueError):
                await service.start_authorization(
                    "tenant-1", "user-1", request
                )

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_state(self, service):
        """Test handling callback with invalid state."""
        callback = OAuthCallbackData(
            code="auth-code",
            state="invalid-state",
        )

        with pytest.raises(ValueError) as exc:
            await service.handle_callback(callback)

        assert "Invalid or expired state" in str(exc.value)

    @pytest.mark.asyncio
    async def test_handle_callback_with_error(self, service):
        """Test handling callback with OAuth error."""
        # Setup state
        service._pending_states["test-state"] = {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "provider": "slack",
        }

        callback = OAuthCallbackData(
            code="",
            state="test-state",
            error="access_denied",
            error_description="User denied access",
        )

        with pytest.raises(ValueError) as exc:
            await service.handle_callback(callback)

        assert "User denied access" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_access_token_valid(self, service):
        """Test getting valid access token."""
        connection_id = uuid4()

        mock_connection = MagicMock()
        mock_connection.access_token_encrypted = "encrypted-token"
        mock_connection.expires_at = datetime.utcnow() + timedelta(hours=1)

        with patch.object(service._repo, "get_connection") as mock_get:
            mock_get.return_value = mock_connection

            with patch.object(service._encryption, "decrypt") as mock_decrypt:
                mock_decrypt.return_value = "access-token"

                token = await service.get_access_token(connection_id, "tenant-1")

                assert token == "access-token"

    @pytest.mark.asyncio
    async def test_get_access_token_expired_refreshes(self, service):
        """Test that expired token triggers refresh."""
        connection_id = uuid4()

        mock_connection = MagicMock()
        mock_connection.access_token_encrypted = "encrypted-token"
        mock_connection.refresh_token_encrypted = "encrypted-refresh"
        mock_connection.expires_at = datetime.utcnow() - timedelta(hours=1)

        with patch.object(service._repo, "get_connection") as mock_get:
            mock_get.return_value = mock_connection

            with patch.object(service, "refresh_token") as mock_refresh:
                mock_refresh.return_value = True

                # Update mock for second get
                mock_connection.expires_at = datetime.utcnow() + timedelta(hours=1)

                with patch.object(service._encryption, "decrypt") as mock_decrypt:
                    mock_decrypt.return_value = "new-access-token"

                    token = await service.get_access_token(connection_id, "tenant-1")

                    mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_connection(self, service):
        """Test revoking a connection."""
        connection_id = uuid4()

        mock_connection = MagicMock()
        mock_connection.provider = "slack"
        mock_connection.access_token_encrypted = "encrypted-token"

        with patch.object(service._repo, "get_connection") as mock_get:
            mock_get.return_value = mock_connection

            with patch.object(service._encryption, "decrypt") as mock_decrypt:
                mock_decrypt.return_value = "access-token"

                with patch.object(service._repo, "update_connection_status") as mock_update:
                    result = await service.revoke_connection(connection_id, "tenant-1")

                    assert result is True
                    mock_update.assert_called_once()


class TestOAuthRepository:
    """Test OAuthRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_connection(self, mock_session):
        """Test creating a connection."""
        from aswa_agents.integrations.oauth.repository import OAuthRepository

        repo = OAuthRepository(session=mock_session)

        await repo.create_connection(
            tenant_id="tenant-1",
            user_id="user-1",
            provider="slack",
            access_token_encrypted="encrypted-token",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_connection_tokens(self, mock_session):
        """Test updating connection tokens."""
        from aswa_agents.integrations.oauth.repository import OAuthRepository

        repo = OAuthRepository(session=mock_session)

        await repo.update_connection_tokens(
            connection_id=uuid4(),
            access_token_encrypted="new-encrypted-token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_oauth.py -v
   ```

2. **Test OAuth flow:**
   ```bash
   # List providers
   curl http://localhost:8000/api/v1/oauth/providers

   # Configure Slack
   curl -X POST http://localhost:8000/api/v1/oauth/providers/configure \
     -H "Content-Type: application/json" \
     -d '{
       "provider": "slack",
       "name": "Company Slack",
       "client_id": "YOUR_CLIENT_ID",
       "client_secret": "YOUR_CLIENT_SECRET"
     }'

   # Start authorization
   curl -X POST http://localhost:8000/api/v1/oauth/authorize \
     -H "Content-Type: application/json" \
     -d '{"provider": "slack"}'
   ```

3. **Test token management:**
   ```bash
   # List connections
   curl http://localhost:8000/api/v1/oauth/connections

   # Refresh token
   curl -X POST http://localhost:8000/api/v1/oauth/connections/{id}/refresh

   # Revoke connection
   curl -X DELETE http://localhost:8000/api/v1/oauth/connections/{id}
   ```

## Next Task

Proceed to `task-9.8.3-agent-webhooks.md` for implementing agent webhooks.
