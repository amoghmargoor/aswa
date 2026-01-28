# Task 6.3.2: Notification Service - Email Notifications

## Context

You are working on the ASWA notification service at `/services/notification-service/`. The core service is complete (Task 6.3.1). Now we need to implement email notifications.

## Objective

Create email notification handling that:
1. Sends transactional emails
2. Uses responsive HTML templates
3. Handles attachments
4. Tracks delivery and opens
5. Manages bounce handling

## Requirements

### 1. Create `/services/notification-service/src/aswa_notifications/channels/email.py`
```python
from typing import Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import aiosmtplib
import structlog

from aswa_notifications.channels.base import BaseChannel
from aswa_notifications.config import Settings

logger = structlog.get_logger()


class EmailChannel(BaseChannel):
    """Email notification channel."""

    def __init__(self, settings: Settings):
        """Initialize email channel.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.from_email = settings.email_from
        self.from_name = settings.email_from_name

    async def send(
        self,
        recipient: dict[str, Any],
        subject: str | None,
        content: dict[str, Any],
        priority: str,
    ) -> dict[str, Any]:
        """Send an email notification.

        Args:
            recipient: Recipient info with 'email' key
            subject: Email subject
            content: Email content with 'body' and optional 'html' keys
            priority: Email priority

        Returns:
            Send result with message_id
        """
        email_address = recipient.get("email")
        if not email_address:
            raise ValueError("Recipient email address required")

        # Build message
        msg = self._build_message(
            to_email=email_address,
            subject=subject or "Notification from ASWA",
            body=content.get("body", ""),
            html=content.get("html"),
            attachments=content.get("attachments", []),
            priority=priority,
        )

        # Add tracking headers
        message_id = self._generate_message_id()
        msg["Message-ID"] = message_id

        # Send email
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user or None,
                password=self.settings.smtp_password or None,
                use_tls=self.settings.smtp_use_tls,
            )

            logger.info(
                "Email sent",
                to=email_address,
                message_id=message_id,
            )

            return {"message_id": message_id, "status": "sent"}

        except aiosmtplib.SMTPException as e:
            logger.error(
                "Email send failed",
                to=email_address,
                error=str(e),
            )
            raise

    async def verify_recipient(
        self,
        recipient: dict[str, Any],
    ) -> bool:
        """Verify email address is valid.

        Args:
            recipient: Recipient info

        Returns:
            True if valid
        """
        email = recipient.get("email", "")

        # Basic validation
        if not email or "@" not in email:
            return False

        # Check format
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def _build_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: str | None = None,
        attachments: list[dict] | None = None,
        priority: str = "normal",
    ) -> MIMEMultipart:
        """Build email message.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Plain text body
            html: Optional HTML body
            attachments: Optional attachments
            priority: Email priority

        Returns:
            MIME message
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Set priority headers
        if priority == "urgent":
            msg["X-Priority"] = "1"
            msg["X-MSMail-Priority"] = "High"
            msg["Importance"] = "High"
        elif priority == "high":
            msg["X-Priority"] = "2"
            msg["X-MSMail-Priority"] = "High"
        elif priority == "low":
            msg["X-Priority"] = "5"
            msg["X-MSMail-Priority"] = "Low"
            msg["Importance"] = "Low"

        # Add plain text part
        text_part = MIMEText(body, "plain", "utf-8")
        msg.attach(text_part)

        # Add HTML part if provided
        if html:
            html_part = MIMEText(html, "html", "utf-8")
            msg.attach(html_part)

        # Add attachments
        if attachments:
            for attachment in attachments:
                self._add_attachment(msg, attachment)

        return msg

    def _add_attachment(
        self,
        msg: MIMEMultipart,
        attachment: dict,
    ) -> None:
        """Add attachment to message.

        Args:
            msg: Message to add to
            attachment: Attachment dict with 'filename', 'content', 'content_type'
        """
        filename = attachment.get("filename", "attachment")
        content = attachment.get("content", b"")
        content_type = attachment.get("content_type", "application/octet-stream")

        maintype, subtype = content_type.split("/", 1)
        part = MIMEBase(maintype, subtype)

        if isinstance(content, str):
            content = content.encode("utf-8")

        part.set_payload(content)
        encoders.encode_base64(part)

        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=filename,
        )

        msg.attach(part)

    def _generate_message_id(self) -> str:
        """Generate a unique message ID.

        Returns:
            Message ID string
        """
        import uuid
        from email.utils import make_msgid
        return make_msgid(domain="aswa.io")


class EmailTemplateBuilder:
    """Builds responsive HTML email templates."""

    BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
        }}
        .header {{
            background-color: #0284c7;
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            padding: 30px;
        }}
        .footer {{
            background-color: #f9fafb;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
        }}
        .button {{
            display: inline-block;
            background-color: #0284c7;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            margin: 10px 0;
        }}
        .button:hover {{
            background-color: #0369a1;
        }}
        .alert {{
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }}
        .alert-info {{
            background-color: #e0f2fe;
            border-left: 4px solid #0284c7;
        }}
        .alert-warning {{
            background-color: #fef3c7;
            border-left: 4px solid #f59e0b;
        }}
        .alert-danger {{
            background-color: #fee2e2;
            border-left: 4px solid #ef4444;
        }}
        .alert-success {{
            background-color: #d1fae5;
            border-left: 4px solid #10b981;
        }}
        @media only screen and (max-width: 600px) {{
            .container {{
                width: 100% !important;
            }}
            .content {{
                padding: 20px !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ASWA</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>This email was sent by ASWA - AI-Powered Document Intelligence</p>
            <p>
                <a href="{{unsubscribe_url}}">Unsubscribe</a> |
                <a href="{{preferences_url}}">Notification Preferences</a>
            </p>
            <p>&copy; {year} ASWA. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    @classmethod
    def build(
        cls,
        title: str,
        content: str,
        unsubscribe_url: str = "#",
        preferences_url: str = "#",
    ) -> str:
        """Build a complete HTML email.

        Args:
            title: Email title
            content: HTML content for body
            unsubscribe_url: Unsubscribe link
            preferences_url: Preferences link

        Returns:
            Complete HTML email
        """
        from datetime import datetime

        return cls.BASE_TEMPLATE.format(
            title=title,
            content=content,
            unsubscribe_url=unsubscribe_url,
            preferences_url=preferences_url,
            year=datetime.now().year,
        )

    @classmethod
    def insight_alert(
        cls,
        insight_title: str,
        insight_type: str,
        severity: str,
        confidence: float,
        description: str,
        document_name: str | None = None,
        view_url: str = "#",
    ) -> str:
        """Build insight alert email.

        Args:
            insight_title: Insight title
            insight_type: Type (risk/opportunity)
            severity: Severity level
            confidence: Confidence score
            description: Insight description
            document_name: Source document name
            view_url: Link to view insight

        Returns:
            HTML content
        """
        alert_class = "alert-danger" if insight_type == "risk" else "alert-success"
        icon = "⚠️" if insight_type == "risk" else "💡"

        content = f"""
        <h2>{icon} New {insight_type.title()} Identified</h2>

        <div class="alert {alert_class}">
            <strong>{insight_title}</strong>
            <p>Severity: {severity.title()} | Confidence: {confidence:.0%}</p>
        </div>

        <p>{description}</p>
        """

        if document_name:
            content += f"<p><strong>Source:</strong> {document_name}</p>"

        content += f"""
        <p style="text-align: center;">
            <a href="{view_url}" class="button">View Insight</a>
        </p>
        """

        return cls.build(f"New {insight_type.title()}: {insight_title}", content)

    @classmethod
    def digest(
        cls,
        period: str,
        date_range: str,
        summary: str,
        new_insights: int,
        new_risks: int,
        new_opportunities: int,
        documents_processed: int,
        top_items: list[dict],
        view_url: str = "#",
    ) -> str:
        """Build digest email.

        Args:
            period: Digest period (daily/weekly)
            date_range: Date range string
            summary: Summary text
            new_insights: New insight count
            new_risks: New risk count
            new_opportunities: New opportunity count
            documents_processed: Documents processed count
            top_items: Top insights/items
            view_url: Dashboard URL

        Returns:
            HTML content
        """
        content = f"""
        <h2>📊 Your {period.title()} Digest</h2>
        <p style="color: #6b7280;">{date_range}</p>

        <p>{summary}</p>

        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 15px; text-align: center; background-color: #f3f4f6;">
                    <div style="font-size: 24px; font-weight: bold; color: #8b5cf6;">{new_insights}</div>
                    <div style="font-size: 12px; color: #6b7280;">New Insights</div>
                </td>
                <td style="padding: 15px; text-align: center; background-color: #f3f4f6;">
                    <div style="font-size: 24px; font-weight: bold; color: #ef4444;">{new_risks}</div>
                    <div style="font-size: 12px; color: #6b7280;">Risks</div>
                </td>
                <td style="padding: 15px; text-align: center; background-color: #f3f4f6;">
                    <div style="font-size: 24px; font-weight: bold; color: #22c55e;">{new_opportunities}</div>
                    <div style="font-size: 12px; color: #6b7280;">Opportunities</div>
                </td>
                <td style="padding: 15px; text-align: center; background-color: #f3f4f6;">
                    <div style="font-size: 24px; font-weight: bold; color: #0284c7;">{documents_processed}</div>
                    <div style="font-size: 12px; color: #6b7280;">Documents</div>
                </td>
            </tr>
        </table>
        """

        if top_items:
            content += "<h3>Top Insights</h3><ul>"
            for item in top_items[:5]:
                icon = "⚠️" if item.get("type") == "risk" else "💡"
                content += f"<li>{icon} <strong>{item.get('title', 'Untitled')}</strong> - {item.get('severity', 'N/A').title()}</li>"
            content += "</ul>"

        content += f"""
        <p style="text-align: center;">
            <a href="{view_url}" class="button">View Dashboard</a>
        </p>
        """

        return cls.build(f"Your {period.title()} ASWA Digest", content)

    @classmethod
    def document_processed(
        cls,
        document_name: str,
        insight_count: int,
        processing_time: str,
        risk_count: int = 0,
        opportunity_count: int = 0,
        view_url: str = "#",
    ) -> str:
        """Build document processed email.

        Args:
            document_name: Document name
            insight_count: Total insights found
            processing_time: Processing duration
            risk_count: Number of risks
            opportunity_count: Number of opportunities
            view_url: Document view URL

        Returns:
            HTML content
        """
        content = f"""
        <h2>✅ Document Processing Complete</h2>

        <div class="alert alert-success">
            <strong>{document_name}</strong> has been processed successfully.
        </div>

        <table style="width: 100%; margin: 20px 0;">
            <tr>
                <td style="padding: 10px;">
                    <strong>Insights Found:</strong> {insight_count}
                </td>
            </tr>
            <tr>
                <td style="padding: 10px;">
                    <strong>Risks:</strong> {risk_count}
                </td>
            </tr>
            <tr>
                <td style="padding: 10px;">
                    <strong>Opportunities:</strong> {opportunity_count}
                </td>
            </tr>
            <tr>
                <td style="padding: 10px;">
                    <strong>Processing Time:</strong> {processing_time}
                </td>
            </tr>
        </table>

        <p style="text-align: center;">
            <a href="{view_url}" class="button">View Document</a>
        </p>
        """

        return cls.build(f"Document Processed: {document_name}", content)

    @classmethod
    def document_failed(
        cls,
        document_name: str,
        error_message: str,
        retry_url: str = "#",
        support_url: str = "#",
    ) -> str:
        """Build document failed email.

        Args:
            document_name: Document name
            error_message: Error description
            retry_url: Retry upload URL
            support_url: Support URL

        Returns:
            HTML content
        """
        content = f"""
        <h2>❌ Document Processing Failed</h2>

        <div class="alert alert-danger">
            <strong>{document_name}</strong> could not be processed.
        </div>

        <p><strong>Error:</strong> {error_message}</p>

        <p>This may be due to:</p>
        <ul>
            <li>Unsupported file format</li>
            <li>Corrupted file</li>
            <li>File too large</li>
            <li>Encrypted or password-protected file</li>
        </ul>

        <p style="text-align: center;">
            <a href="{retry_url}" class="button">Try Again</a>
            <a href="{support_url}" class="button" style="background-color: #6b7280;">Contact Support</a>
        </p>
        """

        return cls.build(f"Processing Failed: {document_name}", content)
```

### 2. Create `/services/notification-service/src/aswa_notifications/services/email_service.py`
```python
from typing import Any
import structlog

from aswa_notifications.channels.email import EmailChannel, EmailTemplateBuilder
from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
)

logger = structlog.get_logger()


class EmailService:
    """High-level email service."""

    def __init__(
        self,
        notification_service: NotificationService,
    ):
        """Initialize email service.

        Args:
            notification_service: Core notification service
        """
        self.notification_service = notification_service

    async def send_insight_alert(
        self,
        tenant_id: str,
        user_id: str,
        insight: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send insight alert email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            insight: Insight data
            view_url: URL to view insight
        """
        # Build HTML content
        html_content = EmailTemplateBuilder.insight_alert(
            insight_title=insight.get("title", "Untitled"),
            insight_type=insight.get("type", "insight"),
            severity=insight.get("severity", "medium"),
            confidence=insight.get("confidence", 0),
            description=insight.get("description", ""),
            document_name=insight.get("document_name"),
            view_url=view_url or "#",
        )

        # Build plain text
        plain_text = f"""
New {insight.get("type", "insight").title()} Identified

{insight.get("title", "Untitled")}
Severity: {insight.get("severity", "medium").title()}
Confidence: {insight.get("confidence", 0):.0%}

{insight.get("description", "")}

View details: {view_url or "N/A"}
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
            priority=self._severity_to_priority(insight.get("severity")),
            subject=f"New {insight.get('type', 'insight').title()}: {insight.get('title', 'Untitled')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"insight_id": insight.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_daily_digest(
        self,
        tenant_id: str,
        user_id: str,
        digest_data: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send daily digest email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            digest_data: Digest data
            view_url: Dashboard URL
        """
        html_content = EmailTemplateBuilder.digest(
            period="daily",
            date_range=digest_data.get("date_range", "Today"),
            summary=digest_data.get("summary", "Here's your daily summary."),
            new_insights=digest_data.get("new_insights", 0),
            new_risks=digest_data.get("new_risks", 0),
            new_opportunities=digest_data.get("new_opportunities", 0),
            documents_processed=digest_data.get("documents_processed", 0),
            top_items=digest_data.get("top_items", []),
            view_url=view_url or "#",
        )

        plain_text = self._build_digest_plain_text(digest_data, "daily")

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DIGEST,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.LOW,
            subject=f"Your Daily ASWA Digest - {digest_data.get('date_range', 'Today')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_weekly_digest(
        self,
        tenant_id: str,
        user_id: str,
        digest_data: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send weekly digest email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            digest_data: Digest data
            view_url: Dashboard URL
        """
        html_content = EmailTemplateBuilder.digest(
            period="weekly",
            date_range=digest_data.get("date_range", "This Week"),
            summary=digest_data.get("summary", "Here's your weekly summary."),
            new_insights=digest_data.get("new_insights", 0),
            new_risks=digest_data.get("new_risks", 0),
            new_opportunities=digest_data.get("new_opportunities", 0),
            documents_processed=digest_data.get("documents_processed", 0),
            top_items=digest_data.get("top_items", []),
            view_url=view_url or "#",
        )

        plain_text = self._build_digest_plain_text(digest_data, "weekly")

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DIGEST,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.LOW,
            subject=f"Your Weekly ASWA Digest - {digest_data.get('date_range', 'This Week')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_processed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send document processed email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
            view_url: Document view URL
        """
        html_content = EmailTemplateBuilder.document_processed(
            document_name=document.get("name", "Unknown"),
            insight_count=document.get("insight_count", 0),
            processing_time=document.get("processing_time", "N/A"),
            risk_count=document.get("risk_count", 0),
            opportunity_count=document.get("opportunity_count", 0),
            view_url=view_url or "#",
        )

        plain_text = f"""
Document Processing Complete

{document.get("name", "Unknown")} has been processed successfully.

Insights Found: {document.get("insight_count", 0)}
Risks: {document.get("risk_count", 0)}
Opportunities: {document.get("opportunity_count", 0)}
Processing Time: {document.get("processing_time", "N/A")}

View document: {view_url or "N/A"}
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_PROCESSED,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.NORMAL,
            subject=f"Document Processed: {document.get('name', 'Unknown')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_failed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
        error: str,
        retry_url: str | None = None,
    ) -> None:
        """Send document failed email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
            error: Error message
            retry_url: Retry URL
        """
        html_content = EmailTemplateBuilder.document_failed(
            document_name=document.get("name", "Unknown"),
            error_message=error,
            retry_url=retry_url or "#",
        )

        plain_text = f"""
Document Processing Failed

{document.get("name", "Unknown")} could not be processed.

Error: {error}

Please try uploading the document again or contact support for assistance.
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_FAILED,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.HIGH,
            subject=f"Processing Failed: {document.get('name', 'Unknown')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    def _severity_to_priority(
        self,
        severity: str | None,
    ) -> NotificationPriority:
        """Map severity to notification priority.

        Args:
            severity: Insight severity

        Returns:
            Notification priority
        """
        mapping = {
            "critical": NotificationPriority.URGENT,
            "high": NotificationPriority.HIGH,
            "medium": NotificationPriority.NORMAL,
            "low": NotificationPriority.LOW,
        }
        return mapping.get(severity or "medium", NotificationPriority.NORMAL)

    def _build_digest_plain_text(
        self,
        digest_data: dict[str, Any],
        period: str,
    ) -> str:
        """Build plain text digest.

        Args:
            digest_data: Digest data
            period: Digest period

        Returns:
            Plain text content
        """
        lines = [
            f"Your {period.title()} ASWA Digest",
            f"{digest_data.get('date_range', '')}",
            "",
            digest_data.get("summary", ""),
            "",
            "Summary:",
            f"- New Insights: {digest_data.get('new_insights', 0)}",
            f"- Risks: {digest_data.get('new_risks', 0)}",
            f"- Opportunities: {digest_data.get('new_opportunities', 0)}",
            f"- Documents Processed: {digest_data.get('documents_processed', 0)}",
        ]

        top_items = digest_data.get("top_items", [])
        if top_items:
            lines.append("")
            lines.append("Top Insights:")
            for item in top_items[:5]:
                lines.append(f"- {item.get('title', 'Untitled')} ({item.get('type', 'N/A')})")

        return "\n".join(lines)
```

## Test Requirements

### Create `/services/notification-service/tests/test_email_channel.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_notifications.channels.email import EmailChannel, EmailTemplateBuilder


class TestEmailChannel:
    @pytest.fixture
    def settings(self):
        settings = MagicMock()
        settings.smtp_host = "localhost"
        settings.smtp_port = 587
        settings.smtp_user = ""
        settings.smtp_password = ""
        settings.smtp_use_tls = False
        settings.email_from = "test@aswa.io"
        settings.email_from_name = "ASWA Test"
        return settings

    @pytest.fixture
    def channel(self, settings):
        return EmailChannel(settings)

    def test_verify_valid_email(self, channel):
        """Test valid email verification."""
        assert channel.verify_recipient({"email": "test@example.com"}) is True
        assert channel.verify_recipient({"email": "user.name@domain.co.uk"}) is True

    def test_verify_invalid_email(self, channel):
        """Test invalid email verification."""
        assert channel.verify_recipient({"email": ""}) is False
        assert channel.verify_recipient({"email": "not-an-email"}) is False
        assert channel.verify_recipient({"email": "@nodomain"}) is False
        assert channel.verify_recipient({}) is False

    def test_build_message(self, channel):
        """Test message building."""
        msg = channel._build_message(
            to_email="test@example.com",
            subject="Test Subject",
            body="Test body content",
            html="<p>Test HTML content</p>",
            priority="high",
        )

        assert msg["To"] == "test@example.com"
        assert msg["Subject"] == "Test Subject"
        assert msg["X-Priority"] == "2"

    @pytest.mark.asyncio
    async def test_send_missing_email(self, channel):
        """Test send fails without email."""
        with pytest.raises(ValueError, match="email address required"):
            await channel.send(
                recipient={},
                subject="Test",
                content={"body": "Test"},
                priority="normal",
            )


class TestEmailTemplateBuilder:
    def test_insight_alert_risk(self):
        """Test risk alert template."""
        html = EmailTemplateBuilder.insight_alert(
            insight_title="Security Risk",
            insight_type="risk",
            severity="critical",
            confidence=0.95,
            description="A critical security risk was identified.",
            document_name="Security Report.pdf",
            view_url="https://app.aswa.io/insights/123",
        )

        assert "Security Risk" in html
        assert "risk" in html.lower()
        assert "critical" in html.lower()
        assert "95%" in html
        assert "Security Report.pdf" in html

    def test_insight_alert_opportunity(self):
        """Test opportunity alert template."""
        html = EmailTemplateBuilder.insight_alert(
            insight_title="Cost Savings",
            insight_type="opportunity",
            severity="high",
            confidence=0.85,
            description="A cost saving opportunity was identified.",
        )

        assert "Cost Savings" in html
        assert "opportunity" in html.lower()
        assert "alert-success" in html

    def test_digest_template(self):
        """Test digest template."""
        html = EmailTemplateBuilder.digest(
            period="daily",
            date_range="January 15, 2024",
            summary="A productive day with several insights.",
            new_insights=10,
            new_risks=3,
            new_opportunities=5,
            documents_processed=8,
            top_items=[
                {"title": "Risk 1", "type": "risk", "severity": "high"},
                {"title": "Opportunity 1", "type": "opportunity", "severity": "medium"},
            ],
        )

        assert "Daily Digest" in html
        assert "January 15, 2024" in html
        assert "10" in html  # new_insights
        assert "Risk 1" in html

    def test_document_processed_template(self):
        """Test document processed template."""
        html = EmailTemplateBuilder.document_processed(
            document_name="Report.pdf",
            insight_count=15,
            processing_time="2m 30s",
            risk_count=5,
            opportunity_count=8,
        )

        assert "Report.pdf" in html
        assert "15" in html
        assert "2m 30s" in html
        assert "successfully" in html.lower()

    def test_document_failed_template(self):
        """Test document failed template."""
        html = EmailTemplateBuilder.document_failed(
            document_name="Corrupted.pdf",
            error_message="File appears to be corrupted",
        )

        assert "Corrupted.pdf" in html
        assert "corrupted" in html.lower()
        assert "alert-danger" in html
```

## Verification

1. Run tests: `pytest tests/test_email_channel.py -v`
2. Test email sending with SMTP server
3. Verify HTML rendering in email clients
4. Test template building
5. Check priority headers
