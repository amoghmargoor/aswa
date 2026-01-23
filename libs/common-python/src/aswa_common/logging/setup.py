"""Structured logging configuration with structlog."""

import logging
from contextvars import ContextVar
from typing import Any
from uuid import UUID

import structlog


# Context variables for request-scoped logging
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_ctx: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
user_id_ctx: ContextVar[UUID | None] = ContextVar("user_id", default=None)


def configure_logging(
    service_name: str,
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structured logging with structlog.

    Args:
        service_name: Name of the service
        log_level: Logging level
        json_output: Whether to output JSON (True for prod, False for dev)
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _add_context_processor,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    # Add service name to all logs
    structlog.contextvars.bind_contextvars(service=service_name)


def _add_context_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add context variables to log event.

    Args:
        logger: The logger instance
        method_name: The logging method name
        event_dict: The event dictionary

    Returns:
        Updated event dictionary
    """
    request_id = request_id_ctx.get()
    tenant_id = tenant_id_ctx.get()
    user_id = user_id_ctx.get()

    if request_id:
        event_dict["requestId"] = request_id
    if tenant_id:
        event_dict["tenantId"] = str(tenant_id)
    if user_id:
        event_dict["userId"] = str(user_id)

    return event_dict


class LoggerContextVar:
    """Context manager for setting logging context variables."""

    @classmethod
    def set(
        cls,
        request_id: str | None = None,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> None:
        """Set context variables.

        Args:
            request_id: Optional request ID
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        if request_id:
            request_id_ctx.set(request_id)
        if tenant_id:
            tenant_id_ctx.set(tenant_id)
        if user_id:
            user_id_ctx.set(user_id)

    @classmethod
    def clear(cls) -> None:
        """Clear all context variables."""
        request_id_ctx.set(None)
        tenant_id_ctx.set(None)
        user_id_ctx.set(None)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured bound logger
    """
    return structlog.get_logger(name)
