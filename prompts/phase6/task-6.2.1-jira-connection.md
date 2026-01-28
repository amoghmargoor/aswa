# Task 6.2.1: Jira Integration - Connection Setup

## Context

You are working on the ASWA integration service at `/services/integration-service/`. The base integration service is complete (Tasks 6.1.1-6.1.2). Now we need to implement the Jira connection and OAuth flow.

## Objective

Create Jira connection management that:
1. Supports Jira Cloud OAuth 2.0
2. Manages project configuration
3. Handles token refresh automatically
4. Provides connection status monitoring
5. Maps ASWA insights to Jira fields

## Requirements

### 1. Create `/services/integration-service/src/aswa_integrations/jira/__init__.py`
```python
from .connection import JiraConnectionManager
from .oauth import JiraOAuthHandler
from .project_config import JiraProjectConfig
from .field_mapper import JiraFieldMapper

__all__ = [
    "JiraConnectionManager",
    "JiraOAuthHandler",
    "JiraProjectConfig",
    "JiraFieldMapper",
]
```

### 2. Create `/services/integration-service/src/aswa_integrations/jira/oauth.py`
```python
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
```

### 3. Create `/services/integration-service/src/aswa_integrations/jira/connection.py`
```python
from datetime import datetime
from typing import Any
import httpx
from pydantic import BaseModel
import structlog

from aswa_integrations.jira.oauth import JiraOAuthHandler, JiraTokens

logger = structlog.get_logger()


class JiraConnectionStatus(BaseModel):
    """Jira connection status."""
    connected: bool
    cloud_id: str | None = None
    site_name: str | None = None
    user_email: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None
    error: str | None = None


class JiraProject(BaseModel):
    """Jira project information."""
    id: str
    key: str
    name: str
    project_type: str
    avatar_url: str | None = None


class JiraConnectionManager:
    """Manages Jira connections."""

    API_BASE = "https://api.atlassian.com/ex/jira"

    def __init__(self, oauth_handler: JiraOAuthHandler):
        """Initialize connection manager.

        Args:
            oauth_handler: OAuth handler instance
        """
        self.oauth_handler = oauth_handler

    async def get_connection_status(
        self,
        tenant_id: str,
    ) -> JiraConnectionStatus:
        """Get connection status for a tenant.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            Connection status
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)

        if not tokens:
            return JiraConnectionStatus(connected=False)

        try:
            # Verify connection by fetching user info
            user_info = await self._get_user_info(tokens)

            return JiraConnectionStatus(
                connected=True,
                cloud_id=tokens.cloud_id,
                site_name=user_info.get("displayName"),
                user_email=user_info.get("emailAddress"),
                scopes=tokens.scope.split(" ") if tokens.scope else [],
                expires_at=tokens.expires_at,
            )

        except Exception as e:
            logger.error(
                "Connection status check failed",
                tenant_id=tenant_id,
                error=str(e),
            )
            return JiraConnectionStatus(
                connected=False,
                error=str(e),
            )

    async def list_projects(
        self,
        tenant_id: str,
    ) -> list[JiraProject]:
        """List accessible Jira projects.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            List of projects
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/project",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )

            if not response.is_success:
                logger.error(
                    "Failed to list projects",
                    status=response.status_code,
                )
                return []

            data = response.json()

        return [
            JiraProject(
                id=p["id"],
                key=p["key"],
                name=p["name"],
                project_type=p.get("projectTypeKey", "software"),
                avatar_url=p.get("avatarUrls", {}).get("48x48"),
            )
            for p in data
        ]

    async def get_project(
        self,
        tenant_id: str,
        project_key: str,
    ) -> JiraProject | None:
        """Get a specific Jira project.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            Project or None
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/project/{project_key}",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )

            if not response.is_success:
                return None

            p = response.json()

        return JiraProject(
            id=p["id"],
            key=p["key"],
            name=p["name"],
            project_type=p.get("projectTypeKey", "software"),
            avatar_url=p.get("avatarUrls", {}).get("48x48"),
        )

    async def get_issue_types(
        self,
        tenant_id: str,
        project_key: str,
    ) -> list[dict[str, Any]]:
        """Get issue types for a project.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            List of issue types
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/project/{project_key}",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                params={"expand": "issueTypes"},
            )

            if not response.is_success:
                return []

            data = response.json()

        return [
            {
                "id": it["id"],
                "name": it["name"],
                "description": it.get("description", ""),
                "subtask": it.get("subtask", False),
            }
            for it in data.get("issueTypes", [])
        ]

    async def get_priorities(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Get available priorities.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            List of priorities
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/priority",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )

            if not response.is_success:
                return []

            data = response.json()

        return [
            {
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description", ""),
            }
            for p in data
        ]

    async def disconnect(
        self,
        tenant_id: str,
    ) -> bool:
        """Disconnect Jira integration.

        Args:
            tenant_id: ASWA tenant identifier

        Returns:
            True if disconnected
        """
        return await self.oauth_handler.revoke_tokens(tenant_id)

    async def _get_user_info(
        self,
        tokens: JiraTokens,
    ) -> dict[str, Any]:
        """Get current user info.

        Args:
            tokens: OAuth tokens

        Returns:
            User information
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/myself",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            response.raise_for_status()
            return response.json()
```

### 4. Create `/services/integration-service/src/aswa_integrations/jira/project_config.py`
```python
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
import structlog

from aswa_integrations.models.integration import Base

logger = structlog.get_logger()


class JiraProjectConfigDB(Base):
    """Database model for Jira project configuration."""

    __tablename__ = "jira_project_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    project_key = Column(String, nullable=False)
    project_name = Column(String, nullable=False)

    # Issue type mappings
    risk_issue_type = Column(String, default="Bug")
    opportunity_issue_type = Column(String, default="Story")
    default_issue_type = Column(String, default="Task")

    # Priority mappings (severity to Jira priority)
    priority_mapping = Column(JSON, default={
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    })

    # Label configuration
    auto_labels = Column(JSON, default=["aswa", "ai-generated"])
    include_severity_label = Column(Boolean, default=True)
    include_type_label = Column(Boolean, default=True)

    # Custom fields
    custom_field_mappings = Column(JSON, default={})

    # Sync settings
    sync_enabled = Column(Boolean, default=True)
    sync_comments = Column(Boolean, default=True)
    sync_status = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JiraProjectConfigCreate(BaseModel):
    """Schema for creating project configuration."""

    project_key: str = Field(..., min_length=1, max_length=10)
    project_name: str
    risk_issue_type: str = "Bug"
    opportunity_issue_type: str = "Story"
    default_issue_type: str = "Task"
    priority_mapping: dict[str, str] = Field(default_factory=lambda: {
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    })
    auto_labels: list[str] = Field(default_factory=lambda: ["aswa", "ai-generated"])
    include_severity_label: bool = True
    include_type_label: bool = True
    custom_field_mappings: dict[str, str] = Field(default_factory=dict)
    sync_enabled: bool = True
    sync_comments: bool = True
    sync_status: bool = True


class JiraProjectConfigUpdate(BaseModel):
    """Schema for updating project configuration."""

    risk_issue_type: str | None = None
    opportunity_issue_type: str | None = None
    default_issue_type: str | None = None
    priority_mapping: dict[str, str] | None = None
    auto_labels: list[str] | None = None
    include_severity_label: bool | None = None
    include_type_label: bool | None = None
    custom_field_mappings: dict[str, str] | None = None
    sync_enabled: bool | None = None
    sync_comments: bool | None = None
    sync_status: bool | None = None


class JiraProjectConfigResponse(BaseModel):
    """Schema for project configuration response."""

    id: str
    tenant_id: str
    project_key: str
    project_name: str
    risk_issue_type: str
    opportunity_issue_type: str
    default_issue_type: str
    priority_mapping: dict[str, str]
    auto_labels: list[str]
    include_severity_label: bool
    include_type_label: bool
    custom_field_mappings: dict[str, str]
    sync_enabled: bool
    sync_comments: bool
    sync_status: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JiraProjectConfig:
    """Manages Jira project configurations."""

    def __init__(self, session_factory):
        """Initialize project config manager.

        Args:
            session_factory: Database session factory
        """
        self.session_factory = session_factory

    async def create_config(
        self,
        tenant_id: str,
        data: JiraProjectConfigCreate,
    ) -> JiraProjectConfigResponse:
        """Create a project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            data: Configuration data

        Returns:
            Created configuration
        """
        config = JiraProjectConfigDB(
            tenant_id=tenant_id,
            project_key=data.project_key,
            project_name=data.project_name,
            risk_issue_type=data.risk_issue_type,
            opportunity_issue_type=data.opportunity_issue_type,
            default_issue_type=data.default_issue_type,
            priority_mapping=data.priority_mapping,
            auto_labels=data.auto_labels,
            include_severity_label=data.include_severity_label,
            include_type_label=data.include_type_label,
            custom_field_mappings=data.custom_field_mappings,
            sync_enabled=data.sync_enabled,
            sync_comments=data.sync_comments,
            sync_status=data.sync_status,
        )

        async with self.session_factory() as session:
            session.add(config)
            await session.commit()
            await session.refresh(config)

        logger.info(
            "Jira project config created",
            tenant_id=tenant_id,
            project_key=data.project_key,
        )

        return JiraProjectConfigResponse.model_validate(config)

    async def get_config(
        self,
        tenant_id: str,
        project_key: str,
    ) -> JiraProjectConfigResponse | None:
        """Get configuration for a project.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            Configuration or None
        """
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if config:
                return JiraProjectConfigResponse.model_validate(config)
            return None

    async def update_config(
        self,
        tenant_id: str,
        project_key: str,
        data: JiraProjectConfigUpdate,
    ) -> JiraProjectConfigResponse | None:
        """Update project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key
            data: Update data

        Returns:
            Updated configuration or None
        """
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(config, field, value)

            config.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(config)

            return JiraProjectConfigResponse.model_validate(config)

    async def delete_config(
        self,
        tenant_id: str,
        project_key: str,
    ) -> bool:
        """Delete project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            True if deleted
        """
        from sqlalchemy import select, delete

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            await session.execute(
                delete(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.id == config.id
                )
            )
            await session.commit()

            return True
```

### 5. Create `/services/integration-service/src/aswa_integrations/jira/field_mapper.py`
```python
from typing import Any
from pydantic import BaseModel
import structlog

from aswa_integrations.jira.project_config import JiraProjectConfigResponse

logger = structlog.get_logger()


class MappedIssueData(BaseModel):
    """Mapped issue data ready for Jira."""
    summary: str
    description: str
    issue_type: str
    priority: str
    labels: list[str]
    custom_fields: dict[str, Any] = {}


class JiraFieldMapper:
    """Maps ASWA insights to Jira issue fields."""

    def __init__(self, config: JiraProjectConfigResponse):
        """Initialize field mapper.

        Args:
            config: Project configuration
        """
        self.config = config

    def map_insight_to_issue(
        self,
        insight: dict[str, Any],
    ) -> MappedIssueData:
        """Map an ASWA insight to Jira issue fields.

        Args:
            insight: ASWA insight data

        Returns:
            Mapped issue data
        """
        insight_type = insight.get("type", "unknown")
        severity = insight.get("severity", "medium")

        # Determine issue type
        if insight_type == "risk":
            issue_type = self.config.risk_issue_type
        elif insight_type == "opportunity":
            issue_type = self.config.opportunity_issue_type
        else:
            issue_type = self.config.default_issue_type

        # Map priority
        priority = self.config.priority_mapping.get(
            severity,
            "Medium",
        )

        # Build labels
        labels = list(self.config.auto_labels)
        if self.config.include_severity_label:
            labels.append(f"severity:{severity}")
        if self.config.include_type_label:
            labels.append(f"type:{insight_type}")

        # Build description
        description = self._build_description(insight)

        # Map custom fields
        custom_fields = self._map_custom_fields(insight)

        return MappedIssueData(
            summary=self._build_summary(insight),
            description=description,
            issue_type=issue_type,
            priority=priority,
            labels=labels,
            custom_fields=custom_fields,
        )

    def _build_summary(
        self,
        insight: dict[str, Any],
    ) -> str:
        """Build issue summary from insight.

        Args:
            insight: ASWA insight data

        Returns:
            Issue summary
        """
        title = insight.get("title", "Untitled Insight")

        # Prefix with type indicator
        insight_type = insight.get("type", "insight")
        prefix = {
            "risk": "[RISK]",
            "opportunity": "[OPP]",
            "entity": "[ENTITY]",
            "trend": "[TREND]",
        }.get(insight_type, "[INSIGHT]")

        return f"{prefix} {title}"

    def _build_description(
        self,
        insight: dict[str, Any],
    ) -> str:
        """Build issue description from insight.

        Args:
            insight: ASWA insight data

        Returns:
            Formatted description
        """
        lines = []

        # Main description
        description = insight.get("description", "")
        if description:
            lines.append(description)
            lines.append("")

        # Confidence
        confidence = insight.get("confidence", 0)
        lines.append(f"*Confidence:* {confidence:.0%}")

        # Severity
        severity = insight.get("severity")
        if severity:
            lines.append(f"*Severity:* {severity.title()}")

        # Source document
        doc_name = insight.get("document_name")
        if doc_name:
            lines.append(f"*Source:* {doc_name}")

        # Evidence/excerpt
        evidence = insight.get("evidence") or insight.get("excerpt")
        if evidence:
            lines.append("")
            lines.append("h3. Evidence")
            lines.append("{quote}")
            lines.append(evidence)
            lines.append("{quote}")

        # ASWA reference
        lines.append("")
        lines.append("----")
        insight_id = insight.get("id", "unknown")
        lines.append(f"_Generated by ASWA | Insight ID: {insight_id}_")

        return "\n".join(lines)

    def _map_custom_fields(
        self,
        insight: dict[str, Any],
    ) -> dict[str, Any]:
        """Map insight fields to Jira custom fields.

        Args:
            insight: ASWA insight data

        Returns:
            Custom field values
        """
        custom_fields = {}

        for insight_field, jira_field in self.config.custom_field_mappings.items():
            if insight_field in insight:
                custom_fields[jira_field] = insight[insight_field]

        return custom_fields

    def map_status_to_transition(
        self,
        insight_status: str,
        available_transitions: list[dict],
    ) -> str | None:
        """Map ASWA insight status to Jira transition.

        Args:
            insight_status: ASWA insight status
            available_transitions: List of available Jira transitions

        Returns:
            Transition ID or None
        """
        # Default status mappings
        status_map = {
            "new": ["To Do", "Open", "Backlog"],
            "in_progress": ["In Progress", "In Development"],
            "resolved": ["Done", "Resolved", "Closed"],
            "dismissed": ["Won't Do", "Rejected", "Closed"],
        }

        target_statuses = status_map.get(insight_status, [])

        for transition in available_transitions:
            if transition.get("name") in target_statuses:
                return transition.get("id")

        return None
```

## Test Requirements

### Create `/services/integration-service/tests/jira/test_oauth.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from aswa_integrations.jira.oauth import (
    JiraOAuthHandler,
    JiraOAuthConfig,
    JiraTokens,
)


class TestJiraOAuth:
    @pytest.fixture
    def oauth_config(self):
        return JiraOAuthConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://app.aswa.io/jira/callback",
        )

    @pytest.fixture
    def oauth_handler(self, oauth_config):
        credential_manager = MagicMock()
        credential_manager.store_credentials = AsyncMock()
        credential_manager.get_credentials = AsyncMock(return_value=None)
        return JiraOAuthHandler(oauth_config, credential_manager)

    def test_get_authorization_url(self, oauth_handler):
        """Test authorization URL generation."""
        url, state = oauth_handler.get_authorization_url("tenant-123")

        assert "auth.atlassian.com/authorize" in url
        assert "client_id=test-client-id" in url
        assert f"state={state}" in url
        assert len(state) > 20

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self, oauth_handler):
        """Test code exchange with invalid state."""
        with pytest.raises(ValueError, match="Invalid or expired state"):
            await oauth_handler.exchange_code("code123", "invalid-state")

    @pytest.mark.asyncio
    async def test_get_valid_tokens_refresh(self, oauth_handler):
        """Test token refresh when expiring soon."""
        # Mock stored tokens that are about to expire
        expiring_tokens = JiraTokens(
            access_token="old-token",
            refresh_token="refresh-token",
            expires_at=datetime.utcnow() + timedelta(minutes=2),
            scope="read:jira-work",
            cloud_id="cloud-123",
        )

        oauth_handler.credential_manager.get_credentials = AsyncMock(
            return_value={
                "access_token": expiring_tokens.access_token,
                "refresh_token": expiring_tokens.refresh_token,
                "expires_at": expiring_tokens.expires_at.isoformat(),
                "scope": expiring_tokens.scope,
                "cloud_id": expiring_tokens.cloud_id,
            }
        )

        with patch.object(oauth_handler, 'refresh_tokens', new_callable=AsyncMock) as mock_refresh:
            mock_refresh.return_value = JiraTokens(
                access_token="new-token",
                refresh_token="refresh-token",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                scope="read:jira-work",
                cloud_id="cloud-123",
            )

            tokens = await oauth_handler.get_valid_tokens("tenant-123")

            mock_refresh.assert_called_once()
            assert tokens.access_token == "new-token"


class TestJiraFieldMapper:
    def test_map_risk_insight(self):
        """Test mapping risk insight to Jira issue."""
        from aswa_integrations.jira.field_mapper import JiraFieldMapper
        from aswa_integrations.jira.project_config import JiraProjectConfigResponse

        config = JiraProjectConfigResponse(
            id="config-123",
            tenant_id="tenant-123",
            project_key="TEST",
            project_name="Test Project",
            risk_issue_type="Bug",
            opportunity_issue_type="Story",
            default_issue_type="Task",
            priority_mapping={"critical": "Highest", "high": "High"},
            auto_labels=["aswa"],
            include_severity_label=True,
            include_type_label=True,
            custom_field_mappings={},
            sync_enabled=True,
            sync_comments=True,
            sync_status=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mapper = JiraFieldMapper(config)

        insight = {
            "id": "insight-123",
            "type": "risk",
            "title": "Security Vulnerability",
            "description": "Critical security issue found",
            "severity": "critical",
            "confidence": 0.95,
        }

        result = mapper.map_insight_to_issue(insight)

        assert result.issue_type == "Bug"
        assert result.priority == "Highest"
        assert "[RISK]" in result.summary
        assert "severity:critical" in result.labels
        assert "type:risk" in result.labels
```

## Verification

1. Run tests: `pytest tests/jira/ -v`
2. Test OAuth flow with Jira Cloud
3. Verify project listing
4. Test field mapping with sample insights
