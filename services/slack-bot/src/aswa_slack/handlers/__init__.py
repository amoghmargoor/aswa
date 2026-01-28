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
