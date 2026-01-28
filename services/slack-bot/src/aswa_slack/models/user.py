from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class SlackUser:
    """A Slack user linked to ASWA."""
    slack_user_id: str
    slack_team_id: str
    aswa_tenant_id: UUID | None = None
    aswa_user_id: UUID | None = None
    display_name: str = ""
    email: str | None = None
    is_admin: bool = False
    preferences: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_linked(self) -> bool:
        """Check if user is linked to ASWA account."""
        return self.aswa_tenant_id is not None


@dataclass
class SlackWorkspace:
    """A Slack workspace installation."""
    team_id: str
    team_name: str
    aswa_tenant_id: UUID | None = None
    bot_user_id: str = ""
    bot_access_token: str = ""
    installed_at: datetime = field(default_factory=datetime.utcnow)
    installed_by: str = ""
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        """Check if workspace is fully configured."""
        return self.aswa_tenant_id is not None
