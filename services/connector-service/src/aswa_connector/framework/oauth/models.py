"""OAuth models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    SLACK = "slack"
    SALESFORCE = "salesforce"
    MICROSOFT = "microsoft"


class OAuthState(BaseModel):
    """State for OAuth flow."""

    state_id: str
    provider: OAuthProvider
    tenant_id: UUID
    user_id: UUID | None = None
    redirect_uri: str
    scopes: list[str] = Field(default_factory=list)
    connector_type: str | None = None
    connection_id: UUID | None = None  # For re-auth
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None


class OAuthTokens(BaseModel):
    """OAuth tokens."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    expires_in: int | None = None
    scope: str | None = None
    id_token: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if access token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at


class OAuthAuthorizationUrl(BaseModel):
    """OAuth authorization URL response."""

    url: str
    state: str
    provider: OAuthProvider


class OAuthCallbackResult(BaseModel):
    """Result of OAuth callback."""

    success: bool
    tokens: OAuthTokens | None = None
    error: str | None = None
    error_description: str | None = None
    tenant_id: UUID | None = None
    connection_id: UUID | None = None
    connector_type: str | None = None
