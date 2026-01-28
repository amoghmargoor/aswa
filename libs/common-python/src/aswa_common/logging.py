import logging
import sys
import json
import structlog
from datetime import datetime
from typing import Any
import os
import traceback
from contextvars import ContextVar

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")


def add_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add context variables to log entries.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    event_dict["request_id"] = request_id_var.get()
    event_dict["tenant_id"] = tenant_id_var.get()
    event_dict["user_id"] = user_id_var.get()

    trace_id = trace_id_var.get()
    if trace_id:
        event_dict["trace_id"] = trace_id
        event_dict["span_id"] = span_id_var.get()

    return event_dict


def add_service_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add service information to log entries.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    event_dict["service"] = os.environ.get("SERVICE_NAME", "unknown")
    event_dict["environment"] = os.environ.get("ENVIRONMENT", "development")
    event_dict["version"] = os.environ.get("VERSION", "unknown")
    event_dict["host"] = os.environ.get("HOSTNAME", "unknown")

    return event_dict


def format_exception(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Format exception information.

    Args:
        logger: Logger instance
        method_name: Logging method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    exc_info = event_dict.pop("exc_info", None)

    if exc_info:
        if isinstance(exc_info, BaseException):
            event_dict["exception"] = {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
                "stacktrace": "".join(traceback.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )),
            }
        elif exc_info is True:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_type:
                event_dict["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "stacktrace": "".join(traceback.format_exception(
                        exc_type, exc_value, exc_tb
                    )),
                }

    return event_dict


class JSONRenderer:
    """Render logs as JSON."""

    def __call__(
        self,
        logger: logging.Logger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> str:
        """Render log entry as JSON.

        Args:
            logger: Logger instance
            method_name: Logging method name
            event_dict: Event dictionary

        Returns:
            JSON string
        """
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        event_dict["level"] = method_name.upper()

        # Ensure message is at top level
        if "event" in event_dict:
            event_dict["message"] = event_dict.pop("event")

        return json.dumps(event_dict, default=str)


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "aswa",
) -> None:
    """Configure structured logging.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format (json, text)
        service_name: Service name for context
    """
    os.environ["SERVICE_NAME"] = service_name

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        add_context,
        add_service_info,
        format_exception,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger.

    Args:
        name: Logger name (optional)

    Returns:
        Configured logger
    """
    return structlog.get_logger(name)


class LoggingMiddleware:
    """FastAPI middleware for request logging."""

    def __init__(self, app):
        """Initialize middleware.

        Args:
            app: FastAPI application
        """
        self.app = app
        self.logger = get_logger("http")

    async def __call__(self, scope, receive, send):
        """Process request with logging.

        Args:
            scope: ASGI scope
            receive: Receive function
            send: Send function
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import uuid
        import time

        # Generate request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        # Extract tenant from headers
        headers = dict(scope.get("headers", []))
        tenant_id = headers.get(b"x-tenant-id", b"").decode()
        user_id = headers.get(b"x-user-id", b"").decode()

        tenant_id_var.set(tenant_id)
        user_id_var.set(user_id)

        # Extract trace context
        traceparent = headers.get(b"traceparent", b"").decode()
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 3:
                trace_id_var.set(parts[1])
                span_id_var.set(parts[2])

        start_time = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.exception(
                "Request failed",
                path=scope.get("path"),
                method=scope.get("method"),
                exc_info=e,
            )
            raise
        finally:
            duration = time.time() - start_time

            self.logger.info(
                "Request completed",
                path=scope.get("path"),
                method=scope.get("method"),
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                client_ip=scope.get("client", ["unknown"])[0],
            )
