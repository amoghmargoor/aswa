"""Audit logging for Python services."""

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from opentelemetry import trace

logger = structlog.get_logger("audit")


class AuditAction(Enum):
    """Audit action types."""
    # Authentication
    LOGIN = ("login", "User login")
    LOGOUT = ("logout", "User logout")
    LOGIN_FAILED = ("login_failed", "Failed login attempt")

    # Resource operations
    CREATE = ("create", "Resource created")
    READ = ("read", "Resource accessed")
    UPDATE = ("update", "Resource updated")
    DELETE = ("delete", "Resource deleted")

    # Document operations
    DOCUMENT_UPLOAD = ("document_upload", "Document uploaded")
    DOCUMENT_DOWNLOAD = ("document_download", "Document downloaded")
    DOCUMENT_PROCESS = ("document_process", "Document processed")

    # Query operations
    QUERY_EXECUTE = ("query_execute", "Query executed")
    INSIGHT_GENERATE = ("insight_generate", "Insight generated")

    def __init__(self, code: str, description: str):
        self.code = code
        self.description = description


class AuditCategory(Enum):
    """Audit event categories."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    ADMIN = "admin"
    SECURITY = "security"
    SYSTEM = "system"


class AuditResult(Enum):
    """Audit result types."""
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


@dataclass
class AuditEvent:
    """Audit event record."""
    action: AuditAction
    category: AuditCategory
    result: AuditResult = AuditResult.SUCCESS
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    before: Optional[dict] = None
    after: Optional[dict] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data["action"] = self.action.code
        data["category"] = self.category.value
        data["result"] = self.result.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """Audit logging service."""

    def __init__(self, kafka_producer=None, repository=None):
        self.kafka_producer = kafka_producer
        self.repository = repository
        self.topic = "aswa.audit.events"

    async def log(self, event: AuditEvent) -> None:
        """Log an audit event."""
        try:
            # Add trace ID if not set
            if not event.trace_id:
                span = trace.get_current_span()
                if span:
                    ctx = span.get_span_context()
                    if ctx.is_valid:
                        event.trace_id = format(ctx.trace_id, '032x')

            # Compute integrity hash
            event_dict = event.to_dict()
            event_json = json.dumps(event_dict, sort_keys=True, default=str)
            hash_value = hashlib.sha256(event_json.encode()).hexdigest()

            event_with_hash = {
                "event": event_dict,
                "hash": hash_value,
            }

            # Send to Kafka
            if self.kafka_producer:
                await self.kafka_producer.send(
                    self.topic,
                    key=event.tenant_id,
                    value=json.dumps(event_with_hash),
                )

            # Also log to structured logger
            logger.info(
                "audit_event",
                action=event.action.code,
                result=event.result.value,
                user_id=event.user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
            )

        except Exception as e:
            logger.error("Failed to log audit event", error=str(e))

    async def log_action(
        self,
        action: AuditAction,
        category: AuditCategory,
        resource_type: str,
        resource_id: str,
        result: AuditResult = AuditResult.SUCCESS,
        metadata: Optional[dict] = None,
        user_context: Optional[dict] = None,
        request_context: Optional[dict] = None,
    ) -> None:
        """Log an action with context."""
        event = AuditEvent(
            action=action,
            category=category,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            metadata=metadata or {},
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")
            event.user_role = user_context.get("role")

        if request_context:
            event.ip_address = request_context.get("ip_address")
            event.user_agent = request_context.get("user_agent")
            event.session_id = request_context.get("session_id")

        await self.log(event)

    async def log_modification(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        before: Any,
        after: Any,
        user_context: Optional[dict] = None,
    ) -> None:
        """Log a data modification with before/after state."""
        event = AuditEvent(
            action=action,
            category=AuditCategory.DATA_MODIFICATION,
            resource_type=resource_type,
            resource_id=resource_id,
            result=AuditResult.SUCCESS,
            before=before if isinstance(before, dict) else {"value": str(before)},
            after=after if isinstance(after, dict) else {"value": str(after)},
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")

        await self.log(event)

    async def log_failure(
        self,
        action: AuditAction,
        category: AuditCategory,
        resource_type: str,
        resource_id: str,
        error_message: str,
        user_context: Optional[dict] = None,
    ) -> None:
        """Log a failed operation."""
        event = AuditEvent(
            action=action,
            category=category,
            resource_type=resource_type,
            resource_id=resource_id,
            result=AuditResult.FAILURE,
            error_message=error_message,
        )

        if user_context:
            event.tenant_id = user_context.get("tenant_id")
            event.user_id = user_context.get("user_id")
            event.user_email = user_context.get("email")

        await self.log(event)


# FastAPI middleware for audit context
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture request context for audit logging."""

    async def dispatch(self, request: Request, call_next):
        # Extract context for audit logging
        request.state.audit_context = {
            "ip_address": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "session_id": request.headers.get("x-session-id"),
        }

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
