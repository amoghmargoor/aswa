from abc import ABC, abstractmethod
from typing import Any
import structlog

logger = structlog.get_logger()


class BaseChannel(ABC):
    """Base class for notification channels."""

    @abstractmethod
    async def send(
        self,
        recipient: dict[str, Any],
        subject: str | None,
        content: dict[str, Any],
        priority: str,
    ) -> dict[str, Any]:
        """Send a notification.

        Args:
            recipient: Recipient info
            subject: Notification subject
            content: Notification content
            priority: Notification priority

        Returns:
            Send result with message_id
        """
        pass

    @abstractmethod
    async def verify_recipient(
        self,
        recipient: dict[str, Any],
    ) -> bool:
        """Verify recipient is valid.

        Args:
            recipient: Recipient info

        Returns:
            True if valid
        """
        pass
