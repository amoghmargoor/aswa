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
