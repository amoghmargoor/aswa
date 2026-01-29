# Task 9.8.1: Trigger Connectors

## Objective

Implement a connector-based trigger system that allows agents to be activated by various external events including webhooks, scheduled tasks, email, Slack, and custom integrations.

## Prerequisites

- Task 9.1.x completed (Agent Core)
- Integration service infrastructure
- Message queue (Redis/RabbitMQ)

## Implementation

### Step 1: Trigger Connector Interface

```python
# services/agent-service/src/aswa_agents/connectors/base.py
"""Base classes for trigger connectors."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class TriggerType(str, Enum):
    """Types of triggers."""

    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    EMAIL = "email"
    SLACK = "slack"
    DOCUMENT = "document"
    TICKET = "ticket"
    CUSTOM = "custom"


class TriggerStatus(str, Enum):
    """Trigger connector status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class TriggerEvent(BaseModel):
    """Event from a trigger."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    trigger_type: TriggerType
    source: str  # Connector identifier
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: str
    agent_id: str | None = None  # Set if trigger is agent-specific

    # Event data
    event_type: str  # e.g., "email.received", "slack.message"
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Processing hints
    priority: int = 0  # Higher = more urgent
    idempotency_key: str | None = None  # For deduplication


class TriggerConfig(BaseModel):
    """Configuration for a trigger connector."""

    enabled: bool = True
    filter_rules: list[dict[str, Any]] = Field(default_factory=list)
    rate_limit: dict[str, int] | None = None  # e.g., {"requests": 100, "window_seconds": 60}
    retry_config: dict[str, Any] | None = None
    custom_config: dict[str, Any] = Field(default_factory=dict)


class TriggerConnector(ABC):
    """
    Abstract base class for trigger connectors.

    Connectors receive external events and convert them to TriggerEvents.
    """

    def __init__(self, config: TriggerConfig | None = None):
        self.config = config or TriggerConfig()
        self._status = TriggerStatus.INACTIVE
        self._logger = logger.bind(
            component=self.__class__.__name__,
            trigger_type=self.trigger_type.value,
        )
        self._event_handlers: list[Callable[[TriggerEvent], Awaitable[None]]] = []

    @property
    @abstractmethod
    def trigger_type(self) -> TriggerType:
        """Return the trigger type."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return connector name."""
        pass

    @property
    def status(self) -> TriggerStatus:
        """Return current status."""
        return self._status

    @abstractmethod
    async def start(self) -> None:
        """Start the connector."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the connector."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        pass

    def register_handler(
        self,
        handler: Callable[[TriggerEvent], Awaitable[None]],
    ) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)

    async def emit_event(self, event: TriggerEvent) -> None:
        """Emit event to all handlers."""
        if not self.config.enabled:
            return

        # Apply filters
        if not self._matches_filters(event):
            self._logger.debug("Event filtered out", event_type=event.event_type)
            return

        for handler in self._event_handlers:
            try:
                await handler(event)
            except Exception as e:
                self._logger.error(
                    "Handler error",
                    error=str(e),
                    event_id=event.id,
                )

    def _matches_filters(self, event: TriggerEvent) -> bool:
        """Check if event matches filter rules."""
        if not self.config.filter_rules:
            return True

        for rule in self.config.filter_rules:
            if self._evaluate_filter_rule(rule, event):
                return True

        return False

    def _evaluate_filter_rule(
        self,
        rule: dict[str, Any],
        event: TriggerEvent,
    ) -> bool:
        """Evaluate a single filter rule."""
        field = rule.get("field", "")
        operator = rule.get("operator", "equals")
        value = rule.get("value")

        # Get field value from event
        event_value = self._get_nested_value(event.model_dump(), field)

        if operator == "equals":
            return event_value == value
        elif operator == "not_equals":
            return event_value != value
        elif operator == "contains":
            return value in str(event_value)
        elif operator == "starts_with":
            return str(event_value).startswith(str(value))
        elif operator == "in":
            return event_value in value
        elif operator == "exists":
            return event_value is not None

        return False

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get value at nested path."""
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current
```

### Step 2: Webhook Trigger Connector

```python
# services/agent-service/src/aswa_agents/connectors/webhook.py
"""Webhook trigger connector."""

import hashlib
import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
import structlog

from aswa_agents.connectors.base import (
    TriggerConnector,
    TriggerType,
    TriggerEvent,
    TriggerConfig,
    TriggerStatus,
)

logger = structlog.get_logger()


class WebhookConfig(TriggerConfig):
    """Webhook-specific configuration."""

    verify_signature: bool = True
    signature_header: str = "X-Webhook-Signature"
    signature_algorithm: str = "sha256"
    allowed_ips: list[str] | None = None
    max_payload_size: int = 1048576  # 1MB


class WebhookEndpoint(BaseModel):
    """Webhook endpoint configuration."""

    id: str
    tenant_id: str
    agent_id: str | None = None
    path: str
    secret: str
    description: str | None = None
    enabled: bool = True
    created_at: datetime


class WebhookConnector(TriggerConnector):
    """
    Webhook trigger connector.

    Receives HTTP webhook calls and converts them to trigger events.
    """

    def __init__(self, config: WebhookConfig | None = None):
        super().__init__(config or WebhookConfig())
        self.config: WebhookConfig = self.config
        self._endpoints: dict[str, WebhookEndpoint] = {}
        self._router = APIRouter(prefix="/webhooks", tags=["webhooks"])
        self._setup_routes()

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.WEBHOOK

    @property
    def name(self) -> str:
        return "webhook"

    @property
    def router(self) -> APIRouter:
        """Get the FastAPI router for webhook endpoints."""
        return self._router

    def _setup_routes(self) -> None:
        """Setup webhook routes."""

        @self._router.post("/{endpoint_id}")
        async def receive_webhook(
            endpoint_id: str,
            request: Request,
            x_webhook_signature: str | None = Header(None),
        ):
            """Receive incoming webhook."""
            endpoint = self._endpoints.get(endpoint_id)

            if not endpoint or not endpoint.enabled:
                raise HTTPException(status_code=404, detail="Endpoint not found")

            # Get body
            body = await request.body()

            if len(body) > self.config.max_payload_size:
                raise HTTPException(status_code=413, detail="Payload too large")

            # Verify signature
            if self.config.verify_signature:
                if not self._verify_signature(body, x_webhook_signature, endpoint.secret):
                    raise HTTPException(status_code=401, detail="Invalid signature")

            # Check IP allowlist
            if self.config.allowed_ips:
                client_ip = request.client.host
                if client_ip not in self.config.allowed_ips:
                    raise HTTPException(status_code=403, detail="IP not allowed")

            # Parse payload
            try:
                import json
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"raw": body.decode("utf-8", errors="replace")}

            # Create event
            event = TriggerEvent(
                trigger_type=TriggerType.WEBHOOK,
                source=f"webhook:{endpoint_id}",
                tenant_id=endpoint.tenant_id,
                agent_id=endpoint.agent_id,
                event_type="webhook.received",
                payload=payload,
                metadata={
                    "endpoint_id": endpoint_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params),
                },
            )

            # Emit event
            await self.emit_event(event)

            return {"status": "received", "event_id": event.id}

        @self._router.get("/{endpoint_id}/status")
        async def endpoint_status(endpoint_id: str):
            """Get endpoint status."""
            endpoint = self._endpoints.get(endpoint_id)

            if not endpoint:
                raise HTTPException(status_code=404, detail="Endpoint not found")

            return {
                "id": endpoint.id,
                "enabled": endpoint.enabled,
                "path": endpoint.path,
            }

    def _verify_signature(
        self,
        body: bytes,
        signature: str | None,
        secret: str,
    ) -> bool:
        """Verify webhook signature."""
        if not signature:
            return False

        expected = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256 if self.config.signature_algorithm == "sha256" else hashlib.sha1,
        ).hexdigest()

        # Handle prefixed signatures (e.g., "sha256=...")
        if "=" in signature:
            signature = signature.split("=", 1)[1]

        return hmac.compare_digest(expected, signature)

    async def register_endpoint(
        self,
        tenant_id: str,
        endpoint_id: str,
        secret: str,
        agent_id: str | None = None,
        description: str | None = None,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint."""
        endpoint = WebhookEndpoint(
            id=endpoint_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            path=f"/webhooks/{endpoint_id}",
            secret=secret,
            description=description,
            created_at=datetime.utcnow(),
        )

        self._endpoints[endpoint_id] = endpoint

        self._logger.info(
            "Endpoint registered",
            endpoint_id=endpoint_id,
            tenant_id=tenant_id,
        )

        return endpoint

    async def remove_endpoint(self, endpoint_id: str) -> bool:
        """Remove a webhook endpoint."""
        if endpoint_id in self._endpoints:
            del self._endpoints[endpoint_id]
            return True
        return False

    async def start(self) -> None:
        """Start the connector."""
        self._status = TriggerStatus.ACTIVE
        self._logger.info("Webhook connector started")

    async def stop(self) -> None:
        """Stop the connector."""
        self._status = TriggerStatus.INACTIVE
        self._logger.info("Webhook connector stopped")

    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        return {
            "status": self._status.value,
            "endpoints_count": len(self._endpoints),
            "active_endpoints": len([e for e in self._endpoints.values() if e.enabled]),
        }
```

### Step 3: Schedule Trigger Connector

```python
# services/agent-service/src/aswa_agents/connectors/schedule.py
"""Schedule trigger connector."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from croniter import croniter
from pydantic import BaseModel
import structlog

from aswa_agents.connectors.base import (
    TriggerConnector,
    TriggerType,
    TriggerEvent,
    TriggerConfig,
    TriggerStatus,
)

logger = structlog.get_logger()


class ScheduleConfig(TriggerConfig):
    """Schedule-specific configuration."""

    max_concurrent_runs: int = 10
    default_timezone: str = "UTC"
    catch_up_missed: bool = False


class ScheduledTask(BaseModel):
    """Scheduled task definition."""

    id: str
    tenant_id: str
    agent_id: str
    name: str
    description: str | None = None

    # Schedule
    cron_expression: str | None = None  # For cron schedules
    interval_seconds: int | None = None  # For interval schedules
    run_at: datetime | None = None  # For one-time schedules

    # Execution settings
    enabled: bool = True
    timezone: str = "UTC"
    payload: dict[str, Any] = {}

    # State
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0

    created_at: datetime
    updated_at: datetime


class ScheduleConnector(TriggerConnector):
    """
    Schedule trigger connector.

    Triggers agents based on cron expressions or intervals.
    """

    def __init__(self, config: ScheduleConfig | None = None):
        super().__init__(config or ScheduleConfig())
        self.config: ScheduleConfig = self.config
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: asyncio.Task | None = None

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.SCHEDULE

    @property
    def name(self) -> str:
        return "schedule"

    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        self._status = TriggerStatus.ACTIVE
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        self._logger.info("Schedule connector started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self._status = TriggerStatus.INACTIVE
        self._logger.info("Schedule connector stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()

                for task in list(self._tasks.values()):
                    if not task.enabled:
                        continue

                    if task.next_run and task.next_run <= now:
                        await self._execute_task(task)

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Scheduler error", error=str(e))
                await asyncio.sleep(5)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task."""
        try:
            event = TriggerEvent(
                trigger_type=TriggerType.SCHEDULE,
                source=f"schedule:{task.id}",
                tenant_id=task.tenant_id,
                agent_id=task.agent_id,
                event_type="schedule.triggered",
                payload=task.payload,
                metadata={
                    "task_id": task.id,
                    "task_name": task.name,
                    "scheduled_time": task.next_run.isoformat() if task.next_run else None,
                    "run_count": task.run_count + 1,
                },
            )

            await self.emit_event(event)

            # Update task state
            task.last_run = datetime.utcnow()
            task.run_count += 1
            task.next_run = self._calculate_next_run(task)
            task.updated_at = datetime.utcnow()

            self._logger.debug(
                "Task executed",
                task_id=task.id,
                next_run=task.next_run.isoformat() if task.next_run else None,
            )

        except Exception as e:
            self._logger.error(
                "Task execution error",
                task_id=task.id,
                error=str(e),
            )

    def _calculate_next_run(self, task: ScheduledTask) -> datetime | None:
        """Calculate next run time for a task."""
        now = datetime.utcnow()

        if task.cron_expression:
            cron = croniter(task.cron_expression, now)
            return cron.get_next(datetime)

        elif task.interval_seconds:
            return now + timedelta(seconds=task.interval_seconds)

        elif task.run_at:
            # One-time task, disable after run
            if task.run_at <= now:
                task.enabled = False
                return None
            return task.run_at

        return None

    async def register_task(
        self,
        tenant_id: str,
        agent_id: str,
        name: str,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        run_at: datetime | None = None,
        payload: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> ScheduledTask:
        """Register a scheduled task."""
        if not any([cron_expression, interval_seconds, run_at]):
            raise ValueError("Must specify cron_expression, interval_seconds, or run_at")

        task_id = str(uuid4())
        now = datetime.utcnow()

        task = ScheduledTask(
            id=task_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name=name,
            description=description,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            run_at=run_at,
            payload=payload or {},
            created_at=now,
            updated_at=now,
        )

        # Calculate initial next_run
        task.next_run = self._calculate_next_run(task)

        self._tasks[task_id] = task

        self._logger.info(
            "Task registered",
            task_id=task_id,
            agent_id=agent_id,
            next_run=task.next_run.isoformat() if task.next_run else None,
        )

        return task

    async def update_task(
        self,
        task_id: str,
        updates: dict[str, Any],
    ) -> ScheduledTask | None:
        """Update a scheduled task."""
        task = self._tasks.get(task_id)

        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        task.next_run = self._calculate_next_run(task)

        return task

    async def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    async def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a scheduled task."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self,
        tenant_id: str,
        agent_id: str | None = None,
    ) -> list[ScheduledTask]:
        """List scheduled tasks."""
        tasks = [t for t in self._tasks.values() if t.tenant_id == tenant_id]

        if agent_id:
            tasks = [t for t in tasks if t.agent_id == agent_id]

        return sorted(tasks, key=lambda t: t.next_run or datetime.max)

    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        active_tasks = [t for t in self._tasks.values() if t.enabled]
        upcoming = sorted(
            [t for t in active_tasks if t.next_run],
            key=lambda t: t.next_run,
        )[:5]

        return {
            "status": self._status.value,
            "scheduler_running": self._running,
            "total_tasks": len(self._tasks),
            "active_tasks": len(active_tasks),
            "upcoming_tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "next_run": t.next_run.isoformat() if t.next_run else None,
                }
                for t in upcoming
            ],
        }
```

### Step 4: Email Trigger Connector

```python
# services/agent-service/src/aswa_agents/connectors/email.py
"""Email trigger connector."""

import asyncio
from datetime import datetime
from typing import Any

from pydantic import BaseModel
import structlog

from aswa_agents.connectors.base import (
    TriggerConnector,
    TriggerType,
    TriggerEvent,
    TriggerConfig,
    TriggerStatus,
)

logger = structlog.get_logger()


class EmailConfig(TriggerConfig):
    """Email-specific configuration."""

    poll_interval_seconds: int = 60
    max_emails_per_poll: int = 50
    mark_as_read: bool = True
    delete_after_process: bool = False


class EmailSubscription(BaseModel):
    """Email subscription configuration."""

    id: str
    tenant_id: str
    agent_id: str

    # Email source
    email_address: str
    imap_server: str | None = None
    imap_port: int = 993
    use_ssl: bool = True

    # Credentials (encrypted)
    credentials_id: str  # Reference to credential store

    # Filtering
    folder: str = "INBOX"
    filter_from: list[str] | None = None
    filter_subject: str | None = None
    filter_label: str | None = None

    # State
    enabled: bool = True
    last_poll: datetime | None = None
    last_message_id: str | None = None

    created_at: datetime


class EmailConnector(TriggerConnector):
    """
    Email trigger connector.

    Polls email accounts for new messages and triggers agents.
    """

    def __init__(self, config: EmailConfig | None = None):
        super().__init__(config or EmailConfig())
        self.config: EmailConfig = self.config
        self._subscriptions: dict[str, EmailSubscription] = {}
        self._running = False
        self._poller_task: asyncio.Task | None = None

    @property
    def trigger_type(self) -> TriggerType:
        return TriggerType.EMAIL

    @property
    def name(self) -> str:
        return "email"

    async def start(self) -> None:
        """Start the email poller."""
        self._running = True
        self._status = TriggerStatus.ACTIVE
        self._poller_task = asyncio.create_task(self._run_poller())
        self._logger.info("Email connector started")

    async def stop(self) -> None:
        """Stop the email poller."""
        self._running = False
        if self._poller_task:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass
        self._status = TriggerStatus.INACTIVE
        self._logger.info("Email connector stopped")

    async def _run_poller(self) -> None:
        """Main email polling loop."""
        while self._running:
            try:
                for subscription in list(self._subscriptions.values()):
                    if not subscription.enabled:
                        continue

                    try:
                        await self._poll_subscription(subscription)
                    except Exception as e:
                        self._logger.error(
                            "Subscription poll error",
                            subscription_id=subscription.id,
                            error=str(e),
                        )

                await asyncio.sleep(self.config.poll_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Poller error", error=str(e))
                await asyncio.sleep(30)

    async def _poll_subscription(self, subscription: EmailSubscription) -> None:
        """Poll a single email subscription."""
        # Get credentials
        credentials = await self._get_credentials(subscription.credentials_id)

        if not credentials:
            self._logger.warning(
                "Missing credentials",
                subscription_id=subscription.id,
            )
            return

        # Connect to email server
        emails = await self._fetch_emails(subscription, credentials)

        for email_data in emails:
            event = TriggerEvent(
                trigger_type=TriggerType.EMAIL,
                source=f"email:{subscription.id}",
                tenant_id=subscription.tenant_id,
                agent_id=subscription.agent_id,
                event_type="email.received",
                payload={
                    "from": email_data.get("from"),
                    "to": email_data.get("to"),
                    "subject": email_data.get("subject"),
                    "body": email_data.get("body"),
                    "html_body": email_data.get("html_body"),
                    "attachments": email_data.get("attachments", []),
                    "date": email_data.get("date"),
                    "message_id": email_data.get("message_id"),
                },
                metadata={
                    "subscription_id": subscription.id,
                    "email_address": subscription.email_address,
                    "folder": subscription.folder,
                },
                idempotency_key=email_data.get("message_id"),
            )

            await self.emit_event(event)

        # Update subscription state
        subscription.last_poll = datetime.utcnow()
        if emails:
            subscription.last_message_id = emails[-1].get("message_id")

    async def _fetch_emails(
        self,
        subscription: EmailSubscription,
        credentials: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Fetch emails from server."""
        # This is a simplified implementation
        # Production would use aioimaplib or similar

        import imaplib
        import email
        from email.header import decode_header

        emails = []

        try:
            # Connect
            if subscription.use_ssl:
                mail = imaplib.IMAP4_SSL(
                    subscription.imap_server,
                    subscription.imap_port,
                )
            else:
                mail = imaplib.IMAP4(
                    subscription.imap_server,
                    subscription.imap_port,
                )

            # Login
            mail.login(credentials["username"], credentials["password"])

            # Select folder
            mail.select(subscription.folder)

            # Search for unseen emails
            search_criteria = "UNSEEN"
            if subscription.filter_from:
                search_criteria += f' FROM "{subscription.filter_from[0]}"'
            if subscription.filter_subject:
                search_criteria += f' SUBJECT "{subscription.filter_subject}"'

            _, message_numbers = mail.search(None, search_criteria)

            for num in message_numbers[0].split()[:self.config.max_emails_per_poll]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)

                # Parse email
                email_data = self._parse_email(msg)
                emails.append(email_data)

                # Mark as read if configured
                if self.config.mark_as_read:
                    mail.store(num, "+FLAGS", "\\Seen")

            mail.close()
            mail.logout()

        except Exception as e:
            self._logger.error(
                "Email fetch error",
                subscription_id=subscription.id,
                error=str(e),
            )

        return emails

    def _parse_email(self, msg) -> dict[str, Any]:
        """Parse email message."""
        from email.header import decode_header

        def decode_str(value):
            if value is None:
                return ""
            decoded = decode_header(value)
            result = []
            for part, encoding in decoded:
                if isinstance(part, bytes):
                    result.append(part.decode(encoding or "utf-8", errors="replace"))
                else:
                    result.append(part)
            return " ".join(result)

        # Get body
        body = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                elif content_type == "text/html":
                    html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        return {
            "message_id": msg.get("Message-ID"),
            "from": decode_str(msg.get("From")),
            "to": decode_str(msg.get("To")),
            "subject": decode_str(msg.get("Subject")),
            "date": msg.get("Date"),
            "body": body,
            "html_body": html_body,
            "attachments": [],  # TODO: Parse attachments
        }

    async def _get_credentials(self, credentials_id: str) -> dict[str, str] | None:
        """Get credentials from credential store."""
        # TODO: Implement credential service integration
        return None

    async def register_subscription(
        self,
        tenant_id: str,
        agent_id: str,
        email_address: str,
        credentials_id: str,
        imap_server: str | None = None,
        folder: str = "INBOX",
        filter_from: list[str] | None = None,
        filter_subject: str | None = None,
    ) -> EmailSubscription:
        """Register an email subscription."""
        from uuid import uuid4

        subscription = EmailSubscription(
            id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
            email_address=email_address,
            credentials_id=credentials_id,
            imap_server=imap_server or self._guess_imap_server(email_address),
            folder=folder,
            filter_from=filter_from,
            filter_subject=filter_subject,
            created_at=datetime.utcnow(),
        )

        self._subscriptions[subscription.id] = subscription

        self._logger.info(
            "Email subscription registered",
            subscription_id=subscription.id,
            email_address=email_address,
        )

        return subscription

    def _guess_imap_server(self, email_address: str) -> str:
        """Guess IMAP server from email domain."""
        domain = email_address.split("@")[1]

        servers = {
            "gmail.com": "imap.gmail.com",
            "outlook.com": "outlook.office365.com",
            "hotmail.com": "outlook.office365.com",
            "yahoo.com": "imap.mail.yahoo.com",
        }

        return servers.get(domain, f"imap.{domain}")

    async def remove_subscription(self, subscription_id: str) -> bool:
        """Remove an email subscription."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        return {
            "status": self._status.value,
            "poller_running": self._running,
            "subscriptions_count": len(self._subscriptions),
            "active_subscriptions": len(
                [s for s in self._subscriptions.values() if s.enabled]
            ),
        }
```

### Step 5: Connector Registry

```python
# services/agent-service/src/aswa_agents/connectors/registry.py
"""Connector registry for managing trigger connectors."""

from typing import Any

import structlog

from aswa_agents.connectors.base import (
    TriggerConnector,
    TriggerType,
    TriggerEvent,
    TriggerStatus,
)
from aswa_agents.connectors.webhook import WebhookConnector
from aswa_agents.connectors.schedule import ScheduleConnector
from aswa_agents.connectors.email import EmailConnector

logger = structlog.get_logger()


class ConnectorRegistry:
    """
    Registry for managing trigger connectors.

    Provides unified access to all connector types.
    """

    def __init__(self):
        self._connectors: dict[str, TriggerConnector] = {}
        self._event_handler = None
        self._logger = logger.bind(component="ConnectorRegistry")

    def register(self, connector: TriggerConnector) -> None:
        """Register a connector."""
        if connector.name in self._connectors:
            raise ValueError(f"Connector {connector.name} already registered")

        self._connectors[connector.name] = connector

        # Wire up event handler
        if self._event_handler:
            connector.register_handler(self._event_handler)

        self._logger.info(
            "Connector registered",
            name=connector.name,
            type=connector.trigger_type.value,
        )

    def unregister(self, name: str) -> bool:
        """Unregister a connector."""
        if name in self._connectors:
            del self._connectors[name]
            return True
        return False

    def get(self, name: str) -> TriggerConnector | None:
        """Get a connector by name."""
        return self._connectors.get(name)

    def get_by_type(self, trigger_type: TriggerType) -> list[TriggerConnector]:
        """Get connectors by type."""
        return [
            c for c in self._connectors.values()
            if c.trigger_type == trigger_type
        ]

    def list_all(self) -> list[TriggerConnector]:
        """List all registered connectors."""
        return list(self._connectors.values())

    def set_event_handler(self, handler) -> None:
        """Set the global event handler."""
        self._event_handler = handler

        # Update existing connectors
        for connector in self._connectors.values():
            connector.register_handler(handler)

    async def start_all(self) -> None:
        """Start all connectors."""
        for connector in self._connectors.values():
            try:
                await connector.start()
            except Exception as e:
                self._logger.error(
                    "Failed to start connector",
                    name=connector.name,
                    error=str(e),
                )

    async def stop_all(self) -> None:
        """Stop all connectors."""
        for connector in self._connectors.values():
            try:
                await connector.stop()
            except Exception as e:
                self._logger.error(
                    "Failed to stop connector",
                    name=connector.name,
                    error=str(e),
                )

    async def health_check_all(self) -> dict[str, Any]:
        """Health check all connectors."""
        results = {}

        for connector in self._connectors.values():
            try:
                results[connector.name] = await connector.health_check()
            except Exception as e:
                results[connector.name] = {
                    "status": TriggerStatus.ERROR.value,
                    "error": str(e),
                }

        # Overall status
        statuses = [r.get("status") for r in results.values()]
        overall = TriggerStatus.ACTIVE.value

        if TriggerStatus.ERROR.value in statuses:
            overall = TriggerStatus.ERROR.value
        elif all(s == TriggerStatus.INACTIVE.value for s in statuses):
            overall = TriggerStatus.INACTIVE.value

        return {
            "overall": overall,
            "connectors": results,
        }


# Default registry with standard connectors
def create_default_registry() -> ConnectorRegistry:
    """Create registry with default connectors."""
    registry = ConnectorRegistry()

    registry.register(WebhookConnector())
    registry.register(ScheduleConnector())
    registry.register(EmailConnector())

    return registry


# Global registry instance
_registry: ConnectorRegistry | None = None


def get_connector_registry() -> ConnectorRegistry:
    """Get the global connector registry."""
    global _registry
    if _registry is None:
        _registry = create_default_registry()
    return _registry
```

## Test Cases

```python
# services/agent-service/tests/unit/test_trigger_connectors.py
"""Tests for trigger connectors."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from aswa_agents.connectors.base import (
    TriggerConnector,
    TriggerType,
    TriggerEvent,
    TriggerConfig,
    TriggerStatus,
)
from aswa_agents.connectors.webhook import WebhookConnector, WebhookConfig
from aswa_agents.connectors.schedule import ScheduleConnector, ScheduleConfig
from aswa_agents.connectors.email import EmailConnector, EmailConfig
from aswa_agents.connectors.registry import ConnectorRegistry


class TestTriggerEvent:
    """Test TriggerEvent model."""

    def test_create_event(self):
        """Test creating a trigger event."""
        event = TriggerEvent(
            trigger_type=TriggerType.WEBHOOK,
            source="webhook:test",
            tenant_id="tenant-1",
            event_type="webhook.received",
            payload={"key": "value"},
        )

        assert event.trigger_type == TriggerType.WEBHOOK
        assert event.source == "webhook:test"
        assert event.payload == {"key": "value"}
        assert event.id is not None

    def test_event_with_agent(self):
        """Test event with agent ID."""
        event = TriggerEvent(
            trigger_type=TriggerType.SCHEDULE,
            source="schedule:daily",
            tenant_id="tenant-1",
            agent_id="agent-123",
            event_type="schedule.triggered",
        )

        assert event.agent_id == "agent-123"


class TestWebhookConnector:
    """Test WebhookConnector."""

    @pytest.fixture
    def connector(self):
        return WebhookConnector()

    @pytest.mark.asyncio
    async def test_register_endpoint(self, connector):
        """Test registering a webhook endpoint."""
        endpoint = await connector.register_endpoint(
            tenant_id="tenant-1",
            endpoint_id="test-endpoint",
            secret="secret-key",
            agent_id="agent-123",
        )

        assert endpoint.id == "test-endpoint"
        assert endpoint.tenant_id == "tenant-1"
        assert endpoint.path == "/webhooks/test-endpoint"

    @pytest.mark.asyncio
    async def test_remove_endpoint(self, connector):
        """Test removing a webhook endpoint."""
        await connector.register_endpoint(
            tenant_id="tenant-1",
            endpoint_id="test-endpoint",
            secret="secret-key",
        )

        result = await connector.remove_endpoint("test-endpoint")
        assert result is True

        result = await connector.remove_endpoint("nonexistent")
        assert result is False

    def test_verify_signature_valid(self, connector):
        """Test signature verification with valid signature."""
        import hmac
        import hashlib

        body = b'{"test": "data"}'
        secret = "test-secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        result = connector._verify_signature(body, signature, secret)
        assert result is True

    def test_verify_signature_invalid(self, connector):
        """Test signature verification with invalid signature."""
        body = b'{"test": "data"}'
        secret = "test-secret"

        result = connector._verify_signature(body, "invalid-sig", secret)
        assert result is False


class TestScheduleConnector:
    """Test ScheduleConnector."""

    @pytest.fixture
    def connector(self):
        return ScheduleConnector()

    @pytest.mark.asyncio
    async def test_register_cron_task(self, connector):
        """Test registering a cron task."""
        task = await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-123",
            name="Daily Report",
            cron_expression="0 9 * * *",  # 9 AM daily
        )

        assert task.name == "Daily Report"
        assert task.cron_expression == "0 9 * * *"
        assert task.next_run is not None

    @pytest.mark.asyncio
    async def test_register_interval_task(self, connector):
        """Test registering an interval task."""
        task = await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-123",
            name="Hourly Check",
            interval_seconds=3600,
        )

        assert task.interval_seconds == 3600
        assert task.next_run is not None

    @pytest.mark.asyncio
    async def test_register_one_time_task(self, connector):
        """Test registering a one-time task."""
        run_time = datetime.utcnow() + timedelta(hours=1)

        task = await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-123",
            name="One-time Task",
            run_at=run_time,
        )

        assert task.run_at == run_time
        assert task.next_run == run_time

    @pytest.mark.asyncio
    async def test_list_tasks(self, connector):
        """Test listing tasks."""
        await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-1",
            name="Task 1",
            interval_seconds=3600,
        )
        await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-2",
            name="Task 2",
            interval_seconds=3600,
        )
        await connector.register_task(
            tenant_id="tenant-2",
            agent_id="agent-3",
            name="Task 3",
            interval_seconds=3600,
        )

        tasks = await connector.list_tasks("tenant-1")
        assert len(tasks) == 2

        tasks = await connector.list_tasks("tenant-1", agent_id="agent-1")
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_execute_task(self, connector):
        """Test task execution emits event."""
        task = await connector.register_task(
            tenant_id="tenant-1",
            agent_id="agent-123",
            name="Test Task",
            interval_seconds=60,
            payload={"key": "value"},
        )

        events = []
        connector.register_handler(lambda e: events.append(e))

        await connector._execute_task(task)

        assert len(events) == 1
        assert events[0].event_type == "schedule.triggered"
        assert events[0].payload == {"key": "value"}


class TestEmailConnector:
    """Test EmailConnector."""

    @pytest.fixture
    def connector(self):
        return EmailConnector()

    @pytest.mark.asyncio
    async def test_register_subscription(self, connector):
        """Test registering an email subscription."""
        subscription = await connector.register_subscription(
            tenant_id="tenant-1",
            agent_id="agent-123",
            email_address="test@gmail.com",
            credentials_id="cred-123",
        )

        assert subscription.email_address == "test@gmail.com"
        assert subscription.imap_server == "imap.gmail.com"
        assert subscription.folder == "INBOX"

    @pytest.mark.asyncio
    async def test_register_subscription_with_filters(self, connector):
        """Test subscription with filters."""
        subscription = await connector.register_subscription(
            tenant_id="tenant-1",
            agent_id="agent-123",
            email_address="test@example.com",
            credentials_id="cred-123",
            imap_server="mail.example.com",
            folder="Support",
            filter_from=["customer@example.com"],
            filter_subject="[Urgent]",
        )

        assert subscription.folder == "Support"
        assert subscription.filter_from == ["customer@example.com"]
        assert subscription.filter_subject == "[Urgent]"

    def test_guess_imap_server(self, connector):
        """Test IMAP server guessing."""
        assert connector._guess_imap_server("user@gmail.com") == "imap.gmail.com"
        assert connector._guess_imap_server("user@outlook.com") == "outlook.office365.com"
        assert connector._guess_imap_server("user@custom.org") == "imap.custom.org"


class TestConnectorRegistry:
    """Test ConnectorRegistry."""

    @pytest.fixture
    def registry(self):
        return ConnectorRegistry()

    def test_register_connector(self, registry):
        """Test registering a connector."""
        connector = WebhookConnector()
        registry.register(connector)

        assert registry.get("webhook") == connector

    def test_register_duplicate(self, registry):
        """Test registering duplicate connector."""
        registry.register(WebhookConnector())

        with pytest.raises(ValueError):
            registry.register(WebhookConnector())

    def test_get_by_type(self, registry):
        """Test getting connectors by type."""
        registry.register(WebhookConnector())
        registry.register(ScheduleConnector())

        webhooks = registry.get_by_type(TriggerType.WEBHOOK)
        assert len(webhooks) == 1

    @pytest.mark.asyncio
    async def test_start_all(self, registry):
        """Test starting all connectors."""
        webhook = WebhookConnector()
        schedule = ScheduleConnector()

        registry.register(webhook)
        registry.register(schedule)

        await registry.start_all()

        assert webhook.status == TriggerStatus.ACTIVE
        assert schedule.status == TriggerStatus.ACTIVE

        await registry.stop_all()

    @pytest.mark.asyncio
    async def test_health_check_all(self, registry):
        """Test health check for all connectors."""
        registry.register(WebhookConnector())
        registry.register(ScheduleConnector())

        health = await registry.health_check_all()

        assert "overall" in health
        assert "connectors" in health
        assert "webhook" in health["connectors"]
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_trigger_connectors.py -v
   ```

2. **Test webhook connector:**
   ```bash
   # Register endpoint
   curl -X POST http://localhost:8000/api/v1/triggers/webhook/register \
     -H "Content-Type: application/json" \
     -d '{"endpoint_id": "test", "secret": "my-secret"}'

   # Send webhook
   curl -X POST http://localhost:8000/webhooks/test \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: <signature>" \
     -d '{"event": "test"}'
   ```

3. **Test schedule connector:**
   ```python
   from aswa_agents.connectors.schedule import ScheduleConnector

   connector = ScheduleConnector()
   await connector.start()

   task = await connector.register_task(
       tenant_id="test",
       agent_id="agent-123",
       name="Test Task",
       cron_expression="*/5 * * * *",  # Every 5 minutes
   )

   print(f"Next run: {task.next_run}")
   ```

4. **Test connector registry:**
   ```python
   from aswa_agents.connectors.registry import get_connector_registry

   registry = get_connector_registry()
   health = await registry.health_check_all()
   print(health)
   ```

## Next Task

Proceed to `task-9.8.2-integration-oauth.md` for implementing OAuth integration.
