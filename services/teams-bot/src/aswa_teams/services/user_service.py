from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID
import json
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


@dataclass
class TeamsUser:
    """A Teams user."""
    teams_user_id: str
    aswa_tenant_id: UUID | None = None
    aswa_user_id: UUID | None = None
    display_name: str = ""
    preferences: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_linked(self) -> bool:
        return self.aswa_tenant_id is not None


class UserService:
    """Service for managing Teams users."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._prefix = "teams:user"

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def get_user(self, teams_user_id: str) -> TeamsUser | None:
        """Get user by Teams ID."""
        r = await self._get_redis()
        key = f"{self._prefix}:{teams_user_id}"

        data = await r.get(key)
        if data:
            user_data = json.loads(data)
            if user_data.get("aswa_tenant_id"):
                user_data["aswa_tenant_id"] = UUID(user_data["aswa_tenant_id"])
            if user_data.get("aswa_user_id"):
                user_data["aswa_user_id"] = UUID(user_data["aswa_user_id"])
            return TeamsUser(**user_data)
        return None

    async def save_user(self, user: TeamsUser) -> None:
        """Save user to storage."""
        r = await self._get_redis()
        key = f"{self._prefix}:{user.teams_user_id}"

        data = {
            "teams_user_id": user.teams_user_id,
            "aswa_tenant_id": str(user.aswa_tenant_id) if user.aswa_tenant_id else None,
            "aswa_user_id": str(user.aswa_user_id) if user.aswa_user_id else None,
            "display_name": user.display_name,
            "preferences": user.preferences,
            "created_at": user.created_at.isoformat(),
        }

        await r.set(key, json.dumps(data))

    async def get_or_create_user(self, teams_user_id: str) -> TeamsUser:
        """Get or create user."""
        user = await self.get_user(teams_user_id)

        if user is None:
            user = TeamsUser(teams_user_id=teams_user_id)
            await self.save_user(user)

        return user

    async def link_user_to_tenant(
        self,
        teams_user_id: str,
        tenant_id: UUID,
    ) -> TeamsUser:
        """Link user to ASWA tenant."""
        user = await self.get_or_create_user(teams_user_id)
        user.aswa_tenant_id = tenant_id
        await self.save_user(user)
        return user

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
