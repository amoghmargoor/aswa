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
