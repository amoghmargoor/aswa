# Task 5.1.1: Slack Bot - Bolt Python App Setup

## Context

You are building the ASWA Slack integration at `/services/slack-bot/`. This is a new service that will allow users to interact with ASWA through Slack.

## Objective

Create a Slack bot using Bolt for Python that:
1. Connects to Slack workspace
2. Handles authentication and OAuth
3. Manages bot configuration
4. Provides health checks
5. Integrates with query-service

## Requirements

### 1. Create service structure

```
/services/slack-bot/
├── src/
│   └── aswa_slack/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── handlers/
│       │   ├── __init__.py
│       │   ├── commands.py
│       │   ├── events.py
│       │   └── interactions.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── query_client.py
│       │   └── user_service.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── user.py
│       └── utils/
│           ├── __init__.py
│           ├── blocks.py
│           └── formatting.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── handlers/
│       └── test_commands.py
├── pyproject.toml
└── Dockerfile
```

### 2. Create `/services/slack-bot/pyproject.toml`
```toml
[project]
name = "aswa-slack"
version = "0.1.0"
description = "ASWA Slack Bot"
requires-python = ">=3.11"
dependencies = [
    "slack-bolt>=1.18.0",
    "slack-sdk>=3.21.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "structlog>=23.1.0",
    "redis>=5.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 3. Create `/services/slack-bot/src/aswa_slack/__init__.py`
```python
from .app import create_app
from .config import Settings

__all__ = ["create_app", "Settings"]
```

### 4. Create `/services/slack-bot/src/aswa_slack/config.py`
```python
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Slack bot configuration."""

    # Slack credentials
    slack_bot_token: str = Field(..., description="Slack Bot User OAuth Token")
    slack_signing_secret: str = Field(..., description="Slack Signing Secret")
    slack_app_token: str = Field(default="", description="Slack App-Level Token for Socket Mode")

    # OAuth settings
    slack_client_id: str = Field(default="", description="Slack Client ID for OAuth")
    slack_client_secret: str = Field(default="", description="Slack Client Secret")
    slack_oauth_redirect_uri: str = Field(default="", description="OAuth Redirect URI")

    # Service URLs
    query_service_url: str = Field(
        default="http://query-service:8000",
        description="Query service URL"
    )

    # Redis for state management
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis URL"
    )

    # Bot settings
    bot_name: str = Field(default="ASWA", description="Bot display name")
    default_response_timeout: int = Field(default=30, description="Response timeout in seconds")
    max_results_per_message: int = Field(default=5, description="Max results to show")

    # Rate limiting
    rate_limit_per_user: int = Field(default=20, description="Requests per minute per user")
    rate_limit_per_workspace: int = Field(default=100, description="Requests per minute per workspace")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {"env_prefix": "ASWA_SLACK_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
```

### 5. Create `/services/slack-bot/src/aswa_slack/app.py`
```python
import asyncio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk.oauth.installation_store.async_installation_store import AsyncInstallationStore
from slack_sdk.oauth.state_store.async_state_store import AsyncOAuthStateStore
import structlog
import redis.asyncio as redis

from .config import Settings
from .handlers import register_handlers
from .services.query_client import QueryClient

logger = structlog.get_logger()


class RedisInstallationStore(AsyncInstallationStore):
    """Store Slack installations in Redis."""

    def __init__(self, redis_client: redis.Redis, prefix: str = "slack:install"):
        self.redis = redis_client
        self.prefix = prefix

    async def async_save(self, installation):
        key = f"{self.prefix}:{installation.team_id}"
        await self.redis.set(key, installation.to_dict())

    async def async_find_installation(
        self,
        *,
        enterprise_id: str | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
        is_enterprise_install: bool | None = False,
    ):
        if team_id:
            key = f"{self.prefix}:{team_id}"
            data = await self.redis.get(key)
            if data:
                from slack_sdk.oauth.installation_store import Installation
                return Installation(**data)
        return None


class RedisStateStore(AsyncOAuthStateStore):
    """Store OAuth state in Redis."""

    def __init__(self, redis_client: redis.Redis, prefix: str = "slack:oauth"):
        self.redis = redis_client
        self.prefix = prefix
        self.expiration_seconds = 600  # 10 minutes

    async def async_issue(self, *args, **kwargs) -> str:
        import secrets
        state = secrets.token_urlsafe(32)
        key = f"{self.prefix}:{state}"
        await self.redis.setex(key, self.expiration_seconds, "1")
        return state

    async def async_consume(self, state: str) -> bool:
        key = f"{self.prefix}:{state}"
        result = await self.redis.delete(key)
        return result > 0


def create_app(settings: Settings | None = None) -> AsyncApp:
    """Create and configure the Slack Bolt app.

    Args:
        settings: Optional settings, uses defaults if not provided

    Returns:
        Configured AsyncApp
    """
    settings = settings or Settings()

    # Initialize app with or without OAuth
    if settings.slack_client_id and settings.slack_client_secret:
        # OAuth flow for multi-workspace
        redis_client = redis.from_url(settings.redis_url)

        oauth_settings = AsyncOAuthSettings(
            client_id=settings.slack_client_id,
            client_secret=settings.slack_client_secret,
            scopes=[
                "app_mentions:read",
                "channels:history",
                "channels:read",
                "chat:write",
                "commands",
                "groups:history",
                "groups:read",
                "im:history",
                "im:read",
                "im:write",
                "users:read",
            ],
            installation_store=RedisInstallationStore(redis_client),
            state_store=RedisStateStore(redis_client),
            redirect_uri=settings.slack_oauth_redirect_uri or None,
        )

        app = AsyncApp(
            signing_secret=settings.slack_signing_secret,
            oauth_settings=oauth_settings,
        )
    else:
        # Single workspace with bot token
        app = AsyncApp(
            token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )

    # Store settings and services on app
    app._settings = settings
    app._query_client = QueryClient(settings.query_service_url)

    # Register all handlers
    register_handlers(app)

    logger.info("Slack app created", bot_name=settings.bot_name)

    return app


async def run_socket_mode(app: AsyncApp, settings: Settings) -> None:
    """Run the app in Socket Mode.

    Args:
        app: Configured Slack app
        settings: App settings
    """
    if not settings.slack_app_token:
        raise ValueError("SLACK_APP_TOKEN required for Socket Mode")

    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    logger.info("Starting Socket Mode handler")
    await handler.start_async()


async def main():
    """Main entry point."""
    settings = Settings()
    app = create_app(settings)

    if settings.slack_app_token:
        await run_socket_mode(app, settings)
    else:
        # HTTP mode would be handled by ASGI server
        logger.info("App created for HTTP mode")


if __name__ == "__main__":
    asyncio.run(main())
```

### 6. Create `/services/slack-bot/src/aswa_slack/models/user.py`
```python
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
```

### 7. Create `/services/slack-bot/src/aswa_slack/models/__init__.py`
```python
from .user import SlackUser, SlackWorkspace

__all__ = ["SlackUser", "SlackWorkspace"]
```

### 8. Create `/services/slack-bot/src/aswa_slack/services/query_client.py`
```python
from typing import Any
from uuid import UUID
import httpx
import structlog

logger = structlog.get_logger()


class QueryClient:
    """Client for ASWA Query Service."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def query(
        self,
        tenant_id: UUID,
        query: str,
        user_id: str | None = None,
        document_ids: list[UUID] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a query against the query service.

        Args:
            tenant_id: Tenant ID
            query: User query
            user_id: Optional user ID for personalization
            document_ids: Optional document filter
            filters: Optional additional filters

        Returns:
            Query response
        """
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
        }

        if user_id:
            payload["user_id"] = user_id
        if document_ids:
            payload["document_ids"] = [str(d) for d in document_ids]
        if filters:
            payload["filters"] = filters

        try:
            response = await client.post("/api/v1/query", json=payload)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("Query service error", status=e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("Query service connection error", error=str(e))
            raise

    async def search(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search for documents and insights.

        Args:
            tenant_id: Tenant ID
            query: Search query
            limit: Maximum results
            filters: Optional filters

        Returns:
            Search results
        """
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
            "limit": limit,
        }

        if filters:
            payload["filters"] = filters

        try:
            response = await client.post("/api/v1/search", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Search failed", error=str(e))
            raise

    async def get_insights(
        self,
        tenant_id: UUID,
        insight_types: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get recent insights.

        Args:
            tenant_id: Tenant ID
            insight_types: Optional filter by type
            limit: Maximum results

        Returns:
            Insights response
        """
        client = await self._get_client()

        params = {
            "tenant_id": str(tenant_id),
            "limit": limit,
        }

        if insight_types:
            params["types"] = ",".join(insight_types)

        try:
            response = await client.get("/api/v1/insights", params=params)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Get insights failed", error=str(e))
            raise

    async def get_digest(
        self,
        tenant_id: UUID,
        period: str = "daily",
    ) -> dict[str, Any]:
        """Get digest for tenant.

        Args:
            tenant_id: Tenant ID
            period: Digest period (daily, weekly)

        Returns:
            Digest response
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"/api/v1/digest/{tenant_id}",
                params={"period": period}
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Get digest failed", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if query service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

### 9. Create `/services/slack-bot/src/aswa_slack/services/user_service.py`
```python
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
```

### 10. Create `/services/slack-bot/src/aswa_slack/services/__init__.py`
```python
from .query_client import QueryClient
from .user_service import UserService

__all__ = ["QueryClient", "UserService"]
```

### 11. Create `/services/slack-bot/src/aswa_slack/utils/blocks.py`
```python
from typing import Any


def text_block(text: str, block_type: str = "mrkdwn") -> dict:
    """Create a text block.

    Args:
        text: Block text
        block_type: Text type (mrkdwn or plain_text)

    Returns:
        Slack block
    """
    return {
        "type": "section",
        "text": {
            "type": block_type,
            "text": text,
        }
    }


def header_block(text: str) -> dict:
    """Create a header block.

    Args:
        text: Header text

    Returns:
        Slack block
    """
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True,
        }
    }


def divider_block() -> dict:
    """Create a divider block."""
    return {"type": "divider"}


def button_block(
    text: str,
    action_id: str,
    value: str = "",
    style: str | None = None,
) -> dict:
    """Create a button element.

    Args:
        text: Button text
        action_id: Action identifier
        value: Button value
        style: Optional style (primary, danger)

    Returns:
        Button element
    """
    button = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True,
        },
        "action_id": action_id,
        "value": value,
    }

    if style:
        button["style"] = style

    return button


def actions_block(elements: list[dict], block_id: str = "") -> dict:
    """Create an actions block.

    Args:
        elements: List of interactive elements
        block_id: Optional block ID

    Returns:
        Actions block
    """
    block = {
        "type": "actions",
        "elements": elements,
    }

    if block_id:
        block["block_id"] = block_id

    return block


def context_block(elements: list[str]) -> dict:
    """Create a context block.

    Args:
        elements: List of text strings

    Returns:
        Context block
    """
    return {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": text}
            for text in elements
        ]
    }


def input_block(
    label: str,
    action_id: str,
    placeholder: str = "",
    multiline: bool = False,
    optional: bool = False,
) -> dict:
    """Create an input block.

    Args:
        label: Input label
        action_id: Action identifier
        placeholder: Placeholder text
        multiline: Allow multiline input
        optional: Whether input is optional

    Returns:
        Input block
    """
    return {
        "type": "input",
        "optional": optional,
        "label": {
            "type": "plain_text",
            "text": label,
        },
        "element": {
            "type": "plain_text_input",
            "action_id": action_id,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder,
            },
            "multiline": multiline,
        }
    }


def select_block(
    label: str,
    action_id: str,
    options: list[tuple[str, str]],
    placeholder: str = "Select an option",
) -> dict:
    """Create a select block.

    Args:
        label: Select label
        action_id: Action identifier
        options: List of (text, value) tuples
        placeholder: Placeholder text

    Returns:
        Select block
    """
    return {
        "type": "input",
        "label": {
            "type": "plain_text",
            "text": label,
        },
        "element": {
            "type": "static_select",
            "action_id": action_id,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder,
            },
            "options": [
                {
                    "text": {"type": "plain_text", "text": text},
                    "value": value,
                }
                for text, value in options
            ]
        }
    }


def answer_blocks(
    answer: str,
    citations: list[dict] | None = None,
    query: str | None = None,
) -> list[dict]:
    """Create blocks for displaying an answer.

    Args:
        answer: Answer text
        citations: Optional list of citations
        query: Optional original query

    Returns:
        List of blocks
    """
    blocks = []

    if query:
        blocks.append(context_block([f"*Query:* {query}"]))

    blocks.append(text_block(answer))

    if citations:
        blocks.append(divider_block())
        citation_text = "*Sources:*\n"
        for i, citation in enumerate(citations, 1):
            doc_name = citation.get("document_name", "Unknown")
            page = citation.get("page_number")
            if page:
                citation_text += f"[{i}] {doc_name}, p.{page}\n"
            else:
                citation_text += f"[{i}] {doc_name}\n"

        blocks.append(context_block([citation_text]))

    return blocks


def insight_blocks(
    insights: list[dict],
    insight_type: str = "all",
) -> list[dict]:
    """Create blocks for displaying insights.

    Args:
        insights: List of insights
        insight_type: Type filter label

    Returns:
        List of blocks
    """
    blocks = [
        header_block(f"📊 {insight_type.title()} Insights"),
    ]

    for insight in insights:
        title = insight.get("title", "Untitled")
        description = insight.get("description", "")[:200]
        confidence = insight.get("confidence", 0)

        emoji = "⚠️" if insight.get("type") == "risk" else "💡"

        blocks.append(text_block(
            f"{emoji} *{title}*\n{description}"
        ))
        blocks.append(context_block([
            f"Confidence: {confidence:.0%}",
            f"Type: {insight.get('type', 'unknown')}",
        ]))
        blocks.append(divider_block())

    return blocks


def error_blocks(message: str, details: str | None = None) -> list[dict]:
    """Create blocks for error display.

    Args:
        message: Error message
        details: Optional details

    Returns:
        List of blocks
    """
    blocks = [
        text_block(f"❌ *Error:* {message}")
    ]

    if details:
        blocks.append(context_block([details]))

    return blocks


def loading_blocks(message: str = "Processing your request...") -> list[dict]:
    """Create blocks for loading state.

    Args:
        message: Loading message

    Returns:
        List of blocks
    """
    return [
        text_block(f"⏳ {message}")
    ]
```

### 12. Create `/services/slack-bot/src/aswa_slack/utils/formatting.py`
```python
from datetime import datetime
from typing import Any


def format_date(dt: datetime | str) -> str:
    """Format datetime for Slack display.

    Args:
        dt: Datetime or ISO string

    Returns:
        Formatted date string
    """
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

    return dt.strftime("%B %d, %Y at %I:%M %p")


def format_confidence(confidence: float) -> str:
    """Format confidence score.

    Args:
        confidence: Confidence value (0-1)

    Returns:
        Formatted string with emoji
    """
    if confidence >= 0.9:
        return f"🟢 {confidence:.0%}"
    elif confidence >= 0.7:
        return f"🟡 {confidence:.0%}"
    else:
        return f"🔴 {confidence:.0%}"


def format_severity(severity: str) -> str:
    """Format severity with emoji.

    Args:
        severity: Severity level

    Returns:
        Formatted string
    """
    severity_map = {
        "critical": "🔴 Critical",
        "high": "🟠 High",
        "medium": "🟡 Medium",
        "low": "🟢 Low",
    }
    return severity_map.get(severity.lower(), severity)


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def escape_markdown(text: str) -> str:
    """Escape Slack mrkdwn special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    chars = ["*", "_", "~", "`", ">"]
    for char in chars:
        text = text.replace(char, f"\\{char}")
    return text


def format_list(items: list[str], numbered: bool = False) -> str:
    """Format items as a list.

    Args:
        items: List items
        numbered: Use numbers instead of bullets

    Returns:
        Formatted list string
    """
    if numbered:
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    return "\n".join(f"• {item}" for item in items)


def format_key_value(data: dict[str, Any]) -> str:
    """Format dict as key-value pairs.

    Args:
        data: Dictionary to format

    Returns:
        Formatted string
    """
    lines = []
    for key, value in data.items():
        formatted_key = key.replace("_", " ").title()
        lines.append(f"*{formatted_key}:* {value}")
    return "\n".join(lines)
```

### 13. Create `/services/slack-bot/src/aswa_slack/utils/__init__.py`
```python
from .blocks import (
    text_block,
    header_block,
    divider_block,
    button_block,
    actions_block,
    context_block,
    input_block,
    select_block,
    answer_blocks,
    insight_blocks,
    error_blocks,
    loading_blocks,
)
from .formatting import (
    format_date,
    format_confidence,
    format_severity,
    truncate_text,
    escape_markdown,
    format_list,
    format_key_value,
)

__all__ = [
    "text_block",
    "header_block",
    "divider_block",
    "button_block",
    "actions_block",
    "context_block",
    "input_block",
    "select_block",
    "answer_blocks",
    "insight_blocks",
    "error_blocks",
    "loading_blocks",
    "format_date",
    "format_confidence",
    "format_severity",
    "truncate_text",
    "escape_markdown",
    "format_list",
    "format_key_value",
]
```

### 14. Create `/services/slack-bot/src/aswa_slack/handlers/__init__.py`
```python
from slack_bolt.async_app import AsyncApp
import structlog

from .commands import register_commands
from .events import register_events
from .interactions import register_interactions

logger = structlog.get_logger()


def register_handlers(app: AsyncApp) -> None:
    """Register all handlers with the app.

    Args:
        app: Slack Bolt app
    """
    register_commands(app)
    register_events(app)
    register_interactions(app)

    # Error handler
    @app.error
    async def handle_error(error, body, logger):
        logger.error("Unhandled error", error=str(error), body=body)

    logger.info("All handlers registered")
```

## Test Requirements

### Create `/services/slack-bot/tests/__init__.py`

### Create `/services/slack-bot/tests/conftest.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from aswa_slack.config import Settings


@pytest.fixture
def settings():
    """Test settings."""
    return Settings(
        slack_bot_token="xoxb-test-token",
        slack_signing_secret="test-secret",
        query_service_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
    )


@pytest.fixture
def mock_query_client():
    """Mock query client."""
    client = MagicMock()
    client.query = AsyncMock(return_value={
        "answer": "Test answer",
        "citations": [],
        "confidence": 0.8,
    })
    client.search = AsyncMock(return_value={"results": []})
    client.get_insights = AsyncMock(return_value={"insights": []})
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_slack_client():
    """Mock Slack client."""
    client = MagicMock()
    client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "123.456"})
    client.chat_update = AsyncMock(return_value={"ok": True})
    client.users_info = AsyncMock(return_value={
        "ok": True,
        "user": {"id": "U123", "name": "testuser", "real_name": "Test User"}
    })
    return client


@pytest.fixture
def mock_say():
    """Mock say function."""
    return AsyncMock()


@pytest.fixture
def mock_ack():
    """Mock ack function."""
    return AsyncMock()


@pytest.fixture
def sample_command_body():
    """Sample slash command body."""
    return {
        "team_id": "T123",
        "user_id": "U123",
        "user_name": "testuser",
        "channel_id": "C123",
        "command": "/aswa",
        "text": "What are the risks?",
        "response_url": "https://hooks.slack.com/commands/xxx",
    }


@pytest.fixture
def sample_event_body():
    """Sample event body."""
    return {
        "team_id": "T123",
        "event": {
            "type": "app_mention",
            "user": "U123",
            "text": "<@BOTID> What are the latest insights?",
            "channel": "C123",
            "ts": "123.456",
        }
    }
```

### Create `/services/slack-bot/tests/handlers/test_commands.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_slack.handlers.commands import handle_aswa_command


class TestSlashCommands:
    @pytest.mark.asyncio
    async def test_aswa_command_query(
        self,
        mock_ack,
        mock_say,
        sample_command_body,
        mock_query_client,
    ):
        """Test /aswa command with query."""
        with patch("aswa_slack.handlers.commands.get_query_client", return_value=mock_query_client):
            # Would need to set up proper context
            pass

    @pytest.mark.asyncio
    async def test_aswa_command_empty(self, mock_ack, mock_say):
        """Test /aswa command with no text."""
        body = {
            "team_id": "T123",
            "user_id": "U123",
            "text": "",
            "channel_id": "C123",
        }

        # Command should show help when no text provided
        pass

    @pytest.mark.asyncio
    async def test_aswa_command_help(self, mock_ack, mock_say):
        """Test /aswa help command."""
        body = {
            "team_id": "T123",
            "user_id": "U123",
            "text": "help",
            "channel_id": "C123",
        }

        # Should display help message
        pass
```

### Create `/services/slack-bot/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source
COPY src/ src/

# Set Python path
ENV PYTHONPATH=/app/src

# Run the bot
CMD ["python", "-m", "aswa_slack.app"]
```

## Verification

1. Install dependencies: `cd /services/slack-bot && pip install -e ".[dev]"`
2. Run tests: `python -m pytest tests/ -v`
3. Verify imports: `python -c "from aswa_slack import create_app"`
4. Test with Slack: Configure with test workspace and verify connection
