# Task 6.3.1: Notification Service - Core Setup

## Context

You are building the ASWA notification service at `/services/notification-service/`. This service manages all outbound notifications across channels (email, push, in-app).

## Objective

Create a notification service that:
1. Provides unified notification API
2. Manages notification preferences
3. Handles template rendering
4. Supports multiple channels
5. Tracks delivery status

## Requirements

### 1. Create service structure

```
/services/notification-service/
├── src/
│   └── aswa_notifications/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   └── dependencies.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── notification.py
│       │   └── preference.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── notification_service.py
│       │   ├── preference_service.py
│       │   └── template_service.py
│       ├── channels/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── email.py
│       │   └── push.py
│       └── templates/
│           ├── email/
│           └── push/
├── tests/
├── pyproject.toml
└── Dockerfile
```

### 2. Create `/services/notification-service/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aswa-notifications"
version = "0.1.0"
description = "ASWA Notification Service"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "redis>=5.0.0",
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "jinja2>=3.1.0",
    "aiosmtplib>=3.0.0",
    "httpx>=0.25.0",
    "structlog>=23.2.0",
    "celery>=5.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 3. Create `/services/notification-service/src/aswa_notifications/config.py`
```python
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Notification service settings."""

    # Service
    service_name: str = "aswa-notifications"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8005

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_notifications"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/4"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "noreply@aswa.io"
    email_from_name: str = "ASWA"

    # Push notifications
    firebase_credentials_path: str = ""
    apns_key_path: str = ""
    apns_key_id: str = ""
    apns_team_id: str = ""

    # Templates
    template_dir: str = "templates"

    # Rate limiting
    rate_limit_per_user: int = 100  # per hour
    rate_limit_per_tenant: int = 1000  # per hour

    model_config = {
        "env_prefix": "NOTIFICATIONS_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4. Create `/services/notification-service/src/aswa_notifications/models/notification.py`
```python
import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NotificationType(str, Enum):
    """Notification types."""
    INSIGHT_ALERT = "insight_alert"
    DIGEST = "digest"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"
    QUERY_RESPONSE = "query_response"
    SYSTEM_ALERT = "system_alert"
    MENTION = "mention"
    SHARE = "share"


class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    SLACK = "slack"
    TEAMS = "teams"


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class NotificationPriority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationDB(Base):
    """Database model for notifications."""

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    subject = Column(String, nullable=True)
    content = Column(JSON, nullable=False)
    template_id = Column(String, nullable=True)
    template_data = Column(JSON, default={})
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING)
    external_id = Column(String, nullable=True)  # ID from external service
    error = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default={})


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""

    user_id: str
    type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: str | None = None
    content: dict[str, Any] | None = None
    template_id: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationBatch(BaseModel):
    """Schema for batch notifications."""

    user_ids: list[str]
    type: NotificationType
    channels: list[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: str | None = None
    template_id: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    """Schema for notification response."""

    id: str
    tenant_id: str
    user_id: str
    type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority
    subject: str | None
    status: DeliveryStatus
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 5. Create `/services/notification-service/src/aswa_notifications/models/preference.py`
```python
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID

from aswa_notifications.models.notification import Base, NotificationType, NotificationChannel


class NotificationPreferenceDB(Base):
    """Database model for notification preferences."""

    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Global settings
    notifications_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    in_app_enabled = Column(Boolean, default=True)

    # Per-type settings
    type_preferences = Column(JSON, default={})  # {type: {channel: bool}}

    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String, nullable=True)  # "22:00"
    quiet_hours_end = Column(String, nullable=True)  # "08:00"
    quiet_hours_timezone = Column(String, default="UTC")

    # Digest settings
    digest_frequency = Column(String, default="daily")  # daily, weekly, none
    digest_time = Column(String, default="09:00")
    digest_timezone = Column(String, default="UTC")

    # Contact info
    email_address = Column(String, nullable=True)
    push_tokens = Column(JSON, default=[])  # List of device tokens

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PreferenceUpdate(BaseModel):
    """Schema for updating preferences."""

    notifications_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    type_preferences: dict[str, dict[str, bool]] | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    digest_frequency: str | None = None
    digest_time: str | None = None
    digest_timezone: str | None = None
    email_address: str | None = None


class PreferenceResponse(BaseModel):
    """Schema for preference response."""

    id: str
    user_id: str
    notifications_enabled: bool
    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    type_preferences: dict[str, dict[str, bool]]
    quiet_hours_enabled: bool
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    quiet_hours_timezone: str
    digest_frequency: str
    digest_time: str
    digest_timezone: str
    email_address: str | None

    model_config = {"from_attributes": True}
```

### 6. Create `/services/notification-service/src/aswa_notifications/services/template_service.py`
```python
from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import structlog

from aswa_notifications.config import get_settings

logger = structlog.get_logger()


class TemplateService:
    """Manages notification templates."""

    def __init__(self):
        self.settings = get_settings()
        self._env: Environment | None = None
        self._templates: dict[str, dict] = {}

    def initialize(self) -> None:
        """Initialize the template service."""
        template_dir = Path(self.settings.template_dir)

        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Register custom filters
        self._env.filters["format_date"] = self._format_date
        self._env.filters["format_number"] = self._format_number

        logger.info("Template service initialized", template_dir=str(template_dir))

    def _format_date(self, value, format="%B %d, %Y"):
        """Format a date."""
        if isinstance(value, str):
            from datetime import datetime
            value = datetime.fromisoformat(value)
        return value.strftime(format)

    def _format_number(self, value, decimals=0):
        """Format a number."""
        if decimals == 0:
            return f"{int(value):,}"
        return f"{value:,.{decimals}f}"

    def render(
        self,
        template_id: str,
        data: dict[str, Any],
        channel: str = "email",
    ) -> dict[str, str]:
        """Render a template.

        Args:
            template_id: Template identifier
            data: Template data
            channel: Target channel

        Returns:
            Rendered content dict with 'subject', 'body', 'html' keys
        """
        if not self._env:
            self.initialize()

        result = {}

        # Render subject
        try:
            subject_template = self._env.get_template(
                f"{channel}/{template_id}/subject.txt"
            )
            result["subject"] = subject_template.render(**data).strip()
        except Exception:
            result["subject"] = data.get("subject", "Notification")

        # Render plain text body
        try:
            body_template = self._env.get_template(
                f"{channel}/{template_id}/body.txt"
            )
            result["body"] = body_template.render(**data)
        except Exception:
            result["body"] = str(data.get("content", ""))

        # Render HTML body (email only)
        if channel == "email":
            try:
                html_template = self._env.get_template(
                    f"{channel}/{template_id}/body.html"
                )
                result["html"] = html_template.render(**data)
            except Exception:
                result["html"] = None

        return result

    def get_template_info(
        self,
        template_id: str,
    ) -> dict[str, Any] | None:
        """Get template metadata.

        Args:
            template_id: Template identifier

        Returns:
            Template metadata or None
        """
        return self._templates.get(template_id)

    def register_template(
        self,
        template_id: str,
        name: str,
        description: str,
        variables: list[str],
        channels: list[str],
    ) -> None:
        """Register a template.

        Args:
            template_id: Template identifier
            name: Template name
            description: Template description
            variables: Required variables
            channels: Supported channels
        """
        self._templates[template_id] = {
            "id": template_id,
            "name": name,
            "description": description,
            "variables": variables,
            "channels": channels,
        }


# Default templates
DEFAULT_TEMPLATES = {
    "insight_alert": {
        "name": "Insight Alert",
        "description": "Alert for new or updated insights",
        "variables": ["insight_title", "insight_type", "severity", "confidence", "document_name"],
        "channels": ["email", "push", "in_app"],
    },
    "digest_daily": {
        "name": "Daily Digest",
        "description": "Daily summary of insights and activity",
        "variables": ["date", "new_insights", "top_risks", "top_opportunities", "documents_processed"],
        "channels": ["email"],
    },
    "digest_weekly": {
        "name": "Weekly Digest",
        "description": "Weekly summary of insights and activity",
        "variables": ["start_date", "end_date", "summary", "highlights"],
        "channels": ["email"],
    },
    "document_processed": {
        "name": "Document Processed",
        "description": "Notification when document processing completes",
        "variables": ["document_name", "insight_count", "processing_time"],
        "channels": ["email", "push", "in_app"],
    },
    "document_failed": {
        "name": "Document Processing Failed",
        "description": "Notification when document processing fails",
        "variables": ["document_name", "error_message"],
        "channels": ["email", "push", "in_app"],
    },
}
```

### 7. Create `/services/notification-service/src/aswa_notifications/services/notification_service.py`
```python
import uuid
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog

from aswa_notifications.config import get_settings
from aswa_notifications.models.notification import (
    NotificationDB,
    NotificationCreate,
    NotificationBatch,
    NotificationResponse,
    NotificationType,
    NotificationChannel,
    DeliveryStatus,
    Base,
)
from aswa_notifications.models.preference import NotificationPreferenceDB
from aswa_notifications.services.template_service import TemplateService
from aswa_notifications.channels.base import BaseChannel
from aswa_notifications.channels.email import EmailChannel
from aswa_notifications.channels.push import PushChannel

logger = structlog.get_logger()


class NotificationService:
    """Core notification service."""

    def __init__(self):
        self.settings = get_settings()
        self.template_service = TemplateService()
        self._engine = None
        self._session_factory = None
        self._channels: dict[NotificationChannel, BaseChannel] = {}

    async def initialize(self) -> None:
        """Initialize the notification service."""
        self._engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
        )

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self.template_service.initialize()

        # Initialize channels
        self._channels[NotificationChannel.EMAIL] = EmailChannel(self.settings)
        self._channels[NotificationChannel.PUSH] = PushChannel(self.settings)

        logger.info("Notification service initialized")

    async def close(self) -> None:
        """Close connections."""
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Notification service not initialized")
        return self._session_factory()

    async def send(
        self,
        tenant_id: str,
        notification: NotificationCreate,
    ) -> NotificationResponse:
        """Send a notification.

        Args:
            tenant_id: Tenant identifier
            notification: Notification to send

        Returns:
            Created notification
        """
        # Check user preferences
        preferences = await self._get_preferences(tenant_id, notification.user_id)

        if not self._should_send(notification, preferences):
            logger.debug(
                "Notification suppressed by preferences",
                user_id=notification.user_id,
                type=notification.type,
            )
            return None

        # Render content if using template
        content = notification.content or {}
        if notification.template_id:
            rendered = self.template_service.render(
                notification.template_id,
                notification.template_data,
                notification.channel.value,
            )
            content = {
                "subject": rendered.get("subject"),
                "body": rendered.get("body"),
                "html": rendered.get("html"),
            }

        # Create notification record
        notif = NotificationDB(
            tenant_id=tenant_id,
            user_id=notification.user_id,
            type=notification.type,
            channel=notification.channel,
            priority=notification.priority,
            subject=content.get("subject") or notification.subject,
            content=content,
            template_id=notification.template_id,
            template_data=notification.template_data,
            scheduled_at=notification.scheduled_at,
            metadata=notification.metadata,
        )

        async with self._get_session() as session:
            session.add(notif)
            await session.commit()
            await session.refresh(notif)

        # Send immediately if not scheduled
        if not notification.scheduled_at or notification.scheduled_at <= datetime.utcnow():
            await self._deliver(notif, preferences)

        return NotificationResponse.model_validate(notif)

    async def send_batch(
        self,
        tenant_id: str,
        batch: NotificationBatch,
    ) -> list[NotificationResponse]:
        """Send notifications to multiple users.

        Args:
            tenant_id: Tenant identifier
            batch: Batch notification request

        Returns:
            List of created notifications
        """
        results = []

        for user_id in batch.user_ids:
            for channel in batch.channels:
                notification = NotificationCreate(
                    user_id=user_id,
                    type=batch.type,
                    channel=channel,
                    priority=batch.priority,
                    subject=batch.subject,
                    template_id=batch.template_id,
                    template_data=batch.template_data,
                    metadata=batch.metadata,
                )

                result = await self.send(tenant_id, notification)
                if result:
                    results.append(result)

        return results

    async def get_notifications(
        self,
        tenant_id: str,
        user_id: str,
        channel: NotificationChannel | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationResponse]:
        """Get notifications for a user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            channel: Optional channel filter
            status: Optional status filter
            limit: Maximum results
            offset: Result offset

        Returns:
            List of notifications
        """
        async with self._get_session() as session:
            query = select(NotificationDB).where(
                NotificationDB.tenant_id == tenant_id,
                NotificationDB.user_id == user_id,
            )

            if channel:
                query = query.where(NotificationDB.channel == channel)
            if status:
                query = query.where(NotificationDB.status == status)

            query = query.order_by(NotificationDB.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            notifications = result.scalars().all()

            return [NotificationResponse.model_validate(n) for n in notifications]

    async def mark_as_read(
        self,
        tenant_id: str,
        user_id: str,
        notification_ids: list[str],
    ) -> int:
        """Mark notifications as read.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            notification_ids: Notification IDs to mark

        Returns:
            Number of notifications updated
        """
        async with self._get_session() as session:
            result = await session.execute(
                update(NotificationDB)
                .where(
                    NotificationDB.tenant_id == tenant_id,
                    NotificationDB.user_id == user_id,
                    NotificationDB.id.in_(notification_ids),
                    NotificationDB.read_at.is_(None),
                )
                .values(read_at=datetime.utcnow())
            )
            await session.commit()
            return result.rowcount

    async def get_unread_count(
        self,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Get unread notification count.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Unread count
        """
        from sqlalchemy import func

        async with self._get_session() as session:
            result = await session.execute(
                select(func.count(NotificationDB.id)).where(
                    NotificationDB.tenant_id == tenant_id,
                    NotificationDB.user_id == user_id,
                    NotificationDB.channel == NotificationChannel.IN_APP,
                    NotificationDB.read_at.is_(None),
                )
            )
            return result.scalar() or 0

    async def retry_failed(self) -> int:
        """Retry failed notifications.

        Returns:
            Number of retries attempted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationDB).where(
                    NotificationDB.status == DeliveryStatus.FAILED,
                    NotificationDB.retry_count < NotificationDB.max_retries,
                )
            )
            notifications = result.scalars().all()

        count = 0
        for notif in notifications:
            preferences = await self._get_preferences(notif.tenant_id, notif.user_id)
            await self._deliver(notif, preferences, is_retry=True)
            count += 1

        return count

    async def _deliver(
        self,
        notification: NotificationDB,
        preferences: NotificationPreferenceDB | None,
        is_retry: bool = False,
    ) -> None:
        """Deliver a notification.

        Args:
            notification: Notification to deliver
            preferences: User preferences
            is_retry: Whether this is a retry
        """
        channel = self._channels.get(notification.channel)
        if not channel:
            logger.warning("Channel not available", channel=notification.channel)
            return

        try:
            # Get recipient info
            recipient = await self._get_recipient_info(notification, preferences)

            # Send through channel
            result = await channel.send(
                recipient=recipient,
                subject=notification.subject,
                content=notification.content,
                priority=notification.priority.value,
            )

            # Update notification status
            async with self._get_session() as session:
                await session.execute(
                    update(NotificationDB)
                    .where(NotificationDB.id == notification.id)
                    .values(
                        status=DeliveryStatus.SENT,
                        external_id=result.get("message_id"),
                        sent_at=datetime.utcnow(),
                        retry_count=notification.retry_count + (1 if is_retry else 0),
                    )
                )
                await session.commit()

            logger.info(
                "Notification sent",
                notification_id=str(notification.id),
                channel=notification.channel.value,
            )

        except Exception as e:
            logger.error(
                "Notification delivery failed",
                notification_id=str(notification.id),
                error=str(e),
            )

            async with self._get_session() as session:
                await session.execute(
                    update(NotificationDB)
                    .where(NotificationDB.id == notification.id)
                    .values(
                        status=DeliveryStatus.FAILED,
                        error=str(e),
                        retry_count=notification.retry_count + 1,
                    )
                )
                await session.commit()

    def _should_send(
        self,
        notification: NotificationCreate,
        preferences: NotificationPreferenceDB | None,
    ) -> bool:
        """Check if notification should be sent based on preferences.

        Args:
            notification: Notification to check
            preferences: User preferences

        Returns:
            True if should send
        """
        if not preferences:
            return True

        if not preferences.notifications_enabled:
            return False

        # Check channel preference
        channel = notification.channel
        if channel == NotificationChannel.EMAIL and not preferences.email_enabled:
            return False
        if channel == NotificationChannel.PUSH and not preferences.push_enabled:
            return False
        if channel == NotificationChannel.IN_APP and not preferences.in_app_enabled:
            return False

        # Check type preference
        type_prefs = preferences.type_preferences or {}
        if notification.type.value in type_prefs:
            channel_prefs = type_prefs[notification.type.value]
            if channel.value in channel_prefs:
                return channel_prefs[channel.value]

        # Check quiet hours
        if preferences.quiet_hours_enabled:
            if self._is_quiet_hours(preferences):
                # Only suppress non-urgent notifications
                if notification.priority.value != "urgent":
                    return False

        return True

    def _is_quiet_hours(self, preferences: NotificationPreferenceDB) -> bool:
        """Check if currently in quiet hours.

        Args:
            preferences: User preferences

        Returns:
            True if in quiet hours
        """
        from datetime import time
        import pytz

        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False

        tz = pytz.timezone(preferences.quiet_hours_timezone)
        now = datetime.now(tz).time()

        start = time.fromisoformat(preferences.quiet_hours_start)
        end = time.fromisoformat(preferences.quiet_hours_end)

        if start <= end:
            return start <= now <= end
        else:
            # Overnight quiet hours (e.g., 22:00 - 08:00)
            return now >= start or now <= end

    async def _get_preferences(
        self,
        tenant_id: str,
        user_id: str,
    ) -> NotificationPreferenceDB | None:
        """Get user preferences.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Preferences or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def _get_recipient_info(
        self,
        notification: NotificationDB,
        preferences: NotificationPreferenceDB | None,
    ) -> dict[str, Any]:
        """Get recipient info for delivery.

        Args:
            notification: Notification
            preferences: User preferences

        Returns:
            Recipient info
        """
        recipient = {"user_id": notification.user_id}

        if preferences:
            if notification.channel == NotificationChannel.EMAIL:
                recipient["email"] = preferences.email_address
            elif notification.channel == NotificationChannel.PUSH:
                recipient["tokens"] = preferences.push_tokens

        return recipient
```

### 8. Create `/services/notification-service/src/aswa_notifications/channels/base.py`
```python
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
```

## Test Requirements

### Create `/services/notification-service/tests/test_notification_service.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
)


class TestNotificationService:
    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_should_send_enabled(self, service):
        """Test notification allowed when enabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = True
        preferences.email_enabled = True
        preferences.type_preferences = {}
        preferences.quiet_hours_enabled = False

        assert service._should_send(notification, preferences) is True

    @pytest.mark.asyncio
    async def test_should_not_send_disabled(self, service):
        """Test notification blocked when disabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = False

        assert service._should_send(notification, preferences) is False

    @pytest.mark.asyncio
    async def test_should_not_send_channel_disabled(self, service):
        """Test notification blocked when channel disabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = True
        preferences.email_enabled = False

        assert service._should_send(notification, preferences) is False


class TestTemplateService:
    def test_render_template(self):
        """Test template rendering."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()
        # Would need template files to test fully

    def test_format_date_filter(self):
        """Test date formatting filter."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()

        date = datetime(2024, 1, 15)
        formatted = service._format_date(date)

        assert "January" in formatted
        assert "15" in formatted
        assert "2024" in formatted

    def test_format_number_filter(self):
        """Test number formatting filter."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()

        assert service._format_number(1234567) == "1,234,567"
        assert service._format_number(1234.5678, 2) == "1,234.57"
```

## Verification

1. Run tests: `pytest tests/ -v`
2. Test notification sending
3. Verify preference filtering
4. Test template rendering
