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
