# Task 5.2.1: Microsoft Teams Bot Setup

## Context

You are building the ASWA Microsoft Teams integration at `/services/teams-bot/`. This is a new service using the Bot Framework SDK for Python.

## Objective

Create a Teams bot that:
1. Handles message activities
2. Supports proactive messaging
3. Integrates with query-service
4. Manages bot state
5. Provides health checks

## Requirements

### 1. Create service structure

```
/services/teams-bot/
├── src/
│   └── aswa_teams/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── bot.py
│       ├── dialogs/
│       │   ├── __init__.py
│       │   ├── main_dialog.py
│       │   └── query_dialog.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── query_client.py
│       │   └── user_service.py
│       ├── cards/
│       │   ├── __init__.py
│       │   └── adaptive_cards.py
│       └── utils/
│           ├── __init__.py
│           └── formatting.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_bot.py
├── pyproject.toml
└── Dockerfile
```

### 2. Create `/services/teams-bot/pyproject.toml`
```toml
[project]
name = "aswa-teams"
version = "0.1.0"
description = "ASWA Teams Bot"
requires-python = ">=3.11"
dependencies = [
    "botbuilder-core>=4.14.0",
    "botbuilder-dialogs>=4.14.0",
    "botbuilder-integration-aiohttp>=4.14.0",
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

### 3. Create `/services/teams-bot/src/aswa_teams/__init__.py`
```python
from .app import create_app
from .config import Settings
from .bot import ASWABot

__all__ = ["create_app", "Settings", "ASWABot"]
```

### 4. Create `/services/teams-bot/src/aswa_teams/config.py`
```python
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Teams bot configuration."""

    # Bot Framework credentials
    app_id: str = Field(..., description="Microsoft App ID")
    app_password: str = Field(..., description="Microsoft App Password")

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
    default_response_timeout: int = Field(default=30, description="Response timeout")
    max_results_per_message: int = Field(default=5, description="Max results")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=3978, description="Server port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {"env_prefix": "ASWA_TEAMS_", "env_file": ".env"}


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
```

### 5. Create `/services/teams-bot/src/aswa_teams/bot.py`
```python
from typing import Any
from uuid import UUID
import structlog

from botbuilder.core import (
    ActivityHandler,
    ConversationState,
    TurnContext,
    UserState,
    MessageFactory,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    Attachment,
)

from .config import Settings
from .services.query_client import QueryClient
from .services.user_service import UserService
from .cards.adaptive_cards import (
    create_answer_card,
    create_insights_card,
    create_error_card,
    create_welcome_card,
    create_help_card,
)

logger = structlog.get_logger()


class ASWABot(ActivityHandler):
    """ASWA Teams Bot handler."""

    def __init__(
        self,
        settings: Settings,
        conversation_state: ConversationState,
        user_state: UserState,
        query_client: QueryClient,
        user_service: UserService,
    ):
        self.settings = settings
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.query_client = query_client
        self.user_service = user_service

        # State accessors
        self.user_profile_accessor = self.user_state.create_property("UserProfile")
        self.conversation_data_accessor = self.conversation_state.create_property("ConversationData")

    async def on_turn(self, turn_context: TurnContext):
        """Handle each turn."""
        await super().on_turn(turn_context)

        # Save state changes
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ):
        """Handle new members added to conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # Send welcome card
                welcome_card = create_welcome_card(self.settings.bot_name)
                await turn_context.send_activity(
                    MessageFactory.attachment(welcome_card)
                )

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        text = turn_context.activity.text.strip() if turn_context.activity.text else ""
        user_id = turn_context.activity.from_property.id
        conversation_id = turn_context.activity.conversation.id

        logger.info(
            "Message received",
            user_id=user_id,
            text=text[:50] if text else "(empty)",
        )

        # Handle empty message
        if not text:
            await turn_context.send_activity("Please enter a question or type 'help' for assistance.")
            return

        # Handle commands
        lower_text = text.lower()

        if lower_text == "help":
            help_card = create_help_card()
            await turn_context.send_activity(MessageFactory.attachment(help_card))
            return

        if lower_text == "status":
            await self._handle_status(turn_context)
            return

        if lower_text.startswith("link "):
            tenant_id = text[5:].strip()
            await self._handle_link(turn_context, user_id, tenant_id)
            return

        if lower_text == "insights":
            await self._handle_insights(turn_context, user_id)
            return

        if lower_text.startswith("insights "):
            insight_type = text[9:].strip()
            await self._handle_insights(turn_context, user_id, insight_type)
            return

        # Handle as query
        await self._handle_query(turn_context, text, user_id)

    async def _handle_query(
        self,
        turn_context: TurnContext,
        query: str,
        user_id: str,
    ) -> None:
        """Handle a user query.

        Args:
            turn_context: Turn context
            query: User query
            user_id: User identifier
        """
        # Send typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        try:
            # Get user
            user = await self.user_service.get_or_create_user(user_id)

            if not user.is_linked:
                error_card = create_error_card(
                    "Not Connected",
                    "Please link your account first by typing: link <tenant-id>"
                )
                await turn_context.send_activity(MessageFactory.attachment(error_card))
                return

            # Execute query
            result = await self.query_client.query(
                tenant_id=user.aswa_tenant_id,
                query=query,
                user_id=user_id,
            )

            # Create answer card
            answer_card = create_answer_card(
                query=query,
                answer=result.get("answer", "No answer found."),
                citations=result.get("citations", []),
                confidence=result.get("confidence", 0),
                query_id=result.get("query_id", ""),
            )

            await turn_context.send_activity(MessageFactory.attachment(answer_card))

            logger.info(
                "Query answered",
                user_id=user_id,
                query=query[:50],
                confidence=result.get("confidence", 0),
            )

        except Exception as e:
            logger.error("Query failed", error=str(e))
            error_card = create_error_card(
                "Query Failed",
                "Something went wrong. Please try again."
            )
            await turn_context.send_activity(MessageFactory.attachment(error_card))

    async def _handle_status(self, turn_context: TurnContext) -> None:
        """Handle status command."""
        try:
            is_healthy = await self.query_client.health_check()

            if is_healthy:
                await turn_context.send_activity("✅ All systems operational!")
            else:
                await turn_context.send_activity("⚠️ Some services may be unavailable.")

        except Exception:
            await turn_context.send_activity("❌ Unable to check status.")

    async def _handle_link(
        self,
        turn_context: TurnContext,
        user_id: str,
        tenant_id_str: str,
    ) -> None:
        """Handle link command."""
        try:
            tenant_id = UUID(tenant_id_str)

            await self.user_service.link_user_to_tenant(
                teams_user_id=user_id,
                tenant_id=tenant_id,
            )

            await turn_context.send_activity(
                f"✅ Successfully linked to tenant `{tenant_id}`!\n\n"
                "You can now ask questions about your documents."
            )

        except ValueError:
            await turn_context.send_activity(
                "❌ Invalid tenant ID. Please provide a valid UUID."
            )

    async def _handle_insights(
        self,
        turn_context: TurnContext,
        user_id: str,
        insight_type: str = "all",
    ) -> None:
        """Handle insights command."""
        try:
            user = await self.user_service.get_or_create_user(user_id)

            if not user.is_linked:
                await turn_context.send_activity(
                    "❌ Not connected. Use `link <tenant-id>` first."
                )
                return

            types = [insight_type] if insight_type != "all" else None

            result = await self.query_client.get_insights(
                tenant_id=user.aswa_tenant_id,
                insight_types=types,
                limit=self.settings.max_results_per_message,
            )

            insights = result.get("insights", [])

            if not insights:
                await turn_context.send_activity(f"No {insight_type} insights found.")
                return

            insights_card = create_insights_card(insights, insight_type)
            await turn_context.send_activity(MessageFactory.attachment(insights_card))

        except Exception as e:
            logger.error("Insights fetch failed", error=str(e))
            await turn_context.send_activity("❌ Failed to fetch insights.")

    async def on_invoke_activity(self, turn_context: TurnContext) -> Any:
        """Handle invoke activities (adaptive card actions)."""
        activity = turn_context.activity

        if activity.name == "adaptiveCard/action":
            action = activity.value.get("action", {})
            action_type = action.get("type", "")
            action_data = action.get("data", {})

            if action_type == "feedback":
                return await self._handle_feedback_action(turn_context, action_data)
            elif action_type == "refine":
                return await self._handle_refine_action(turn_context, action_data)

        return None

    async def _handle_feedback_action(
        self,
        turn_context: TurnContext,
        data: dict,
    ) -> dict:
        """Handle feedback card action."""
        query_id = data.get("query_id", "")
        feedback = data.get("feedback", "")
        user_id = turn_context.activity.from_property.id

        logger.info(
            "Feedback received",
            query_id=query_id,
            feedback=feedback,
            user_id=user_id,
        )

        return {
            "statusCode": 200,
            "type": "application/vnd.microsoft.activity.message",
            "value": "Thanks for your feedback! 👍",
        }

    async def _handle_refine_action(
        self,
        turn_context: TurnContext,
        data: dict,
    ) -> dict:
        """Handle refine query action."""
        refined_query = data.get("query", "")
        user_id = turn_context.activity.from_property.id

        if refined_query:
            await self._handle_query(turn_context, refined_query, user_id)

        return {"statusCode": 200}
```

### 6. Create `/services/teams-bot/src/aswa_teams/app.py`
```python
import asyncio
from aiohttp import web
from aiohttp.web import Request, Response
import structlog

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    ConversationState,
    MemoryStorage,
    UserState,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity

from .config import Settings
from .bot import ASWABot
from .services.query_client import QueryClient
from .services.user_service import UserService

logger = structlog.get_logger()


def create_app(settings: Settings | None = None) -> web.Application:
    """Create the aiohttp application.

    Args:
        settings: Optional settings

    Returns:
        Configured web application
    """
    settings = settings or Settings()

    # Create adapter
    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.app_id,
        app_password=settings.app_password,
    )
    adapter = BotFrameworkAdapter(adapter_settings)

    # Error handler
    async def on_error(context, error):
        logger.error("Bot error", error=str(error))
        await context.send_activity("Sorry, something went wrong.")

    adapter.on_turn_error = on_error

    # Create state management
    storage = MemoryStorage()  # Use Redis in production
    conversation_state = ConversationState(storage)
    user_state = UserState(storage)

    # Create services
    query_client = QueryClient(settings.query_service_url)
    user_service = UserService(settings.redis_url)

    # Create bot
    bot = ASWABot(
        settings=settings,
        conversation_state=conversation_state,
        user_state=user_state,
        query_client=query_client,
        user_service=user_service,
    )

    # Message handler
    async def messages(req: Request) -> Response:
        if "application/json" in req.headers.get("Content-Type", ""):
            body = await req.json()
        else:
            return Response(status=415)

        activity = Activity().deserialize(body)

        auth_header = req.headers.get("Authorization", "")

        response = await adapter.process_activity(
            activity,
            auth_header,
            bot.on_turn,
        )

        if response:
            return Response(
                body=response.body,
                status=response.status,
            )
        return Response(status=201)

    # Health check
    async def health(req: Request) -> Response:
        return Response(text="OK")

    # Create app
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)

    # Store references
    app["settings"] = settings
    app["bot"] = bot
    app["query_client"] = query_client

    logger.info("Teams bot app created", port=settings.port)

    return app


def run():
    """Run the bot server."""
    settings = Settings()
    app = create_app(settings)

    web.run_app(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
```

### 7. Create `/services/teams-bot/src/aswa_teams/services/query_client.py`
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
    ) -> dict[str, Any]:
        """Execute a query."""
        client = await self._get_client()

        payload = {
            "query": query,
            "tenant_id": str(tenant_id),
        }

        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post("/api/v1/query", json=payload)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("Query failed", error=str(e))
            raise

    async def get_insights(
        self,
        tenant_id: UUID,
        insight_types: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get insights."""
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

### 8. Create `/services/teams-bot/src/aswa_teams/services/user_service.py`
```python
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
```

### 9. Create `/services/teams-bot/src/aswa_teams/services/__init__.py`
```python
from .query_client import QueryClient
from .user_service import UserService, TeamsUser

__all__ = ["QueryClient", "UserService", "TeamsUser"]
```

## Test Requirements

### Create `/services/teams-bot/tests/__init__.py`

### Create `/services/teams-bot/tests/conftest.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from aswa_teams.config import Settings


@pytest.fixture
def settings():
    return Settings(
        app_id="test-app-id",
        app_password="test-password",
        query_service_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
    )


@pytest.fixture
def mock_query_client():
    client = MagicMock()
    client.query = AsyncMock(return_value={
        "answer": "Test answer",
        "citations": [],
        "confidence": 0.8,
        "query_id": "test-123",
    })
    client.get_insights = AsyncMock(return_value={"insights": []})
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_user_service():
    service = MagicMock()
    service.get_or_create_user = AsyncMock()
    service.link_user_to_tenant = AsyncMock()
    return service
```

### Create `/services/teams-bot/tests/test_bot.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_teams.bot import ASWABot
from aswa_teams.services.user_service import TeamsUser


class TestASWABot:
    @pytest.fixture
    def bot(self, settings, mock_query_client, mock_user_service):
        conversation_state = MagicMock()
        conversation_state.create_property = MagicMock(return_value=MagicMock())
        user_state = MagicMock()
        user_state.create_property = MagicMock(return_value=MagicMock())

        return ASWABot(
            settings=settings,
            conversation_state=conversation_state,
            user_state=user_state,
            query_client=mock_query_client,
            user_service=mock_user_service,
        )

    @pytest.fixture
    def turn_context(self):
        context = MagicMock()
        context.activity.text = "What are the risks?"
        context.activity.from_property.id = "user-123"
        context.activity.conversation.id = "conv-123"
        context.send_activity = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_handle_help_command(self, bot, turn_context):
        """Test help command."""
        turn_context.activity.text = "help"

        await bot.on_message_activity(turn_context)

        turn_context.send_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_status_command(self, bot, turn_context):
        """Test status command."""
        turn_context.activity.text = "status"

        await bot.on_message_activity(turn_context)

        turn_context.send_activity.assert_called()

    @pytest.mark.asyncio
    async def test_handle_query_not_linked(
        self,
        bot,
        turn_context,
        mock_user_service,
    ):
        """Test query when user not linked."""
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=None,
        )

        await bot.on_message_activity(turn_context)

        # Should send error about not being connected
        turn_context.send_activity.assert_called()

    @pytest.mark.asyncio
    async def test_handle_query_success(
        self,
        bot,
        turn_context,
        mock_user_service,
        mock_query_client,
    ):
        """Test successful query."""
        tenant_id = uuid4()
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=tenant_id,
        )

        await bot.on_message_activity(turn_context)

        mock_query_client.query.assert_called_once()
        turn_context.send_activity.assert_called()
```

### Create `/services/teams-bot/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

ENV PYTHONPATH=/app/src

EXPOSE 3978

CMD ["python", "-m", "aswa_teams.app"]
```

## Verification

1. Install dependencies: `cd /services/teams-bot && pip install -e ".[dev]"`
2. Run tests: `python -m pytest tests/ -v`
3. Verify imports: `python -c "from aswa_teams import create_app"`
