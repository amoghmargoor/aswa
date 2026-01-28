from typing import Any
from uuid import UUID
import redis.asyncio as redis
import json
import structlog

from ..models.user import SlackUser, SlackWorkspace

logger = structlog.get_logger()


class UserService:
    """Service for managing Slack users and workspaces."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._user_prefix = "slack:user"
        self._workspace_prefix = "slack:workspace"

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def get_user(
        self,
        slack_user_id: str,
        slack_team_id: str,
    ) -> SlackUser | None:
        """Get user by Slack IDs.

        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack team ID

        Returns:
            SlackUser if found
        """
        r = await self._get_redis()
        key = f"{self._user_prefix}:{slack_team_id}:{slack_user_id}"

        data = await r.get(key)
        if data:
            user_data = json.loads(data)
            return SlackUser(**user_data)
        return None

    async def save_user(self, user: SlackUser) -> None:
        """Save user to storage.

        Args:
            user: User to save
        """
        r = await self._get_redis()
        key = f"{self._user_prefix}:{user.slack_team_id}:{user.slack_user_id}"

        data = {
            "slack_user_id": user.slack_user_id,
            "slack_team_id": user.slack_team_id,
            "aswa_tenant_id": str(user.aswa_tenant_id) if user.aswa_tenant_id else None,
            "aswa_user_id": str(user.aswa_user_id) if user.aswa_user_id else None,
            "display_name": user.display_name,
            "email": user.email,
            "is_admin": user.is_admin,
            "preferences": user.preferences,
            "created_at": user.created_at.isoformat(),
            "last_active": user.last_active.isoformat(),
        }

        await r.set(key, json.dumps(data))
        logger.debug("User saved", user_id=user.slack_user_id)

    async def get_or_create_user(
        self,
        slack_user_id: str,
        slack_team_id: str,
        display_name: str = "",
    ) -> SlackUser:
        """Get user or create if not exists.

        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack team ID
            display_name: Display name

        Returns:
            SlackUser
        """
        user = await self.get_user(slack_user_id, slack_team_id)

        if user is None:
            user = SlackUser(
                slack_user_id=slack_user_id,
                slack_team_id=slack_team_id,
                display_name=display_name,
            )
            await self.save_user(user)
            logger.info("New user created", user_id=slack_user_id)

        return user

    async def link_user_to_tenant(
        self,
        slack_user_id: str,
        slack_team_id: str,
        tenant_id: UUID,
        user_id: UUID | None = None,
    ) -> SlackUser:
        """Link Slack user to ASWA tenant.

        Args:
            slack_user_id: Slack user ID
            slack_team_id: Slack team ID
            tenant_id: ASWA tenant ID
            user_id: Optional ASWA user ID

        Returns:
            Updated SlackUser
        """
        user = await self.get_or_create_user(slack_user_id, slack_team_id)
        user.aswa_tenant_id = tenant_id
        user.aswa_user_id = user_id
        await self.save_user(user)

        logger.info(
            "User linked to tenant",
            user_id=slack_user_id,
            tenant_id=str(tenant_id),
        )

        return user

    async def get_workspace(self, team_id: str) -> SlackWorkspace | None:
        """Get workspace by team ID.

        Args:
            team_id: Slack team ID

        Returns:
            SlackWorkspace if found
        """
        r = await self._get_redis()
        key = f"{self._workspace_prefix}:{team_id}"

        data = await r.get(key)
        if data:
            ws_data = json.loads(data)
            return SlackWorkspace(**ws_data)
        return None

    async def save_workspace(self, workspace: SlackWorkspace) -> None:
        """Save workspace to storage.

        Args:
            workspace: Workspace to save
        """
        r = await self._get_redis()
        key = f"{self._workspace_prefix}:{workspace.team_id}"

        data = {
            "team_id": workspace.team_id,
            "team_name": workspace.team_name,
            "aswa_tenant_id": str(workspace.aswa_tenant_id) if workspace.aswa_tenant_id else None,
            "bot_user_id": workspace.bot_user_id,
            "installed_at": workspace.installed_at.isoformat(),
            "installed_by": workspace.installed_by,
            "settings": workspace.settings,
        }

        await r.set(key, json.dumps(data))
        logger.debug("Workspace saved", team_id=workspace.team_id)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
