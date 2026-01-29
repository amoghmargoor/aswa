"""Integration action blocks for external services."""

import time
from typing import Any, ClassVar

import structlog

from aswa_agents.actions.blocks.base import (
    ActionBlock,
    ActionCategory,
    ActionContext,
    ActionResult,
    ActionSchema,
    ActionStatus,
)

logger = structlog.get_logger()


class SendSlackAction(ActionBlock):
    """Send message to Slack channel."""

    action_type: ClassVar[str] = "send_slack"
    category: ClassVar[ActionCategory] = ActionCategory.INTEGRATION
    display_name: ClassVar[str] = "Send Slack Message"
    description: ClassVar[str] = "Send a message to a Slack channel"
    icon: ClassVar[str] = "message-square"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["channel"],
        properties={
            "channel": {
                "type": "string",
                "description": "Slack channel (e.g., #general)",
            },
            "message_template": {
                "type": "string",
                "description": "Message template with {{variable}} placeholders",
            },
            "blocks": {
                "type": "array",
                "description": "Slack Block Kit blocks for rich formatting",
            },
            "mention_users": {
                "type": "array",
                "items": {"type": "string"},
                "description": "User IDs or @mentions to include",
            },
            "thread_ts": {
                "type": "string",
                "description": "Thread timestamp for reply",
            },
        },
    )

    def get_required_connectors(self) -> list[str]:
        """Requires Slack connector."""
        return ["slack"]

    async def execute(self, context: ActionContext) -> ActionResult:
        """Send Slack message."""
        start_time = time.time()

        try:
            channel = self.config.get("channel")
            message_template = self.config.get("message_template", "{{summary}}")
            blocks = self.config.get("blocks")
            mention_users = self.config.get("mention_users", [])
            thread_ts = self.config.get("thread_ts")

            # Render message template
            message = self._render_template(message_template, context)

            # Add mentions
            if mention_users:
                mentions = " ".join(
                    f"<@{user}>" if not user.startswith("@") else user
                    for user in mention_users
                )
                message = f"{mentions} {message}"

            # Get Slack client from context or create one
            slack_token = context.get_secret("SLACK_BOT_TOKEN")
            if not slack_token:
                return self._create_result(
                    status=ActionStatus.FAILED,
                    error="Slack token not configured",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Send message (would use actual Slack SDK)
            message_id = await self._send_message(
                token=slack_token,
                channel=channel,
                text=message,
                blocks=blocks,
                thread_ts=thread_ts,
            )

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Slack message sent",
                channel=channel,
                message_id=message_id,
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={
                    "message_id": message_id,
                    "channel": channel,
                    "thread_ts": thread_ts,
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Slack send failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _render_template(self, template: str, context: ActionContext) -> str:
        """Render message template with context variables."""
        import re

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)

            # Check previous outputs first
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and var_name in output:
                    return str(output[var_name])

            # Check variables
            if var_name in context.variables:
                return str(context.variables[var_name])

            # Check trigger data
            if var_name in context.trigger_data:
                return str(context.trigger_data[var_name])

            return f"{{{{{var_name}}}}}"

        return re.sub(r"\{\{(\w+)\}\}", replace_var, template)

    async def _send_message(
        self,
        token: str,
        channel: str,
        text: str,
        blocks: list | None = None,
        thread_ts: str | None = None,
    ) -> str:
        """Send message to Slack."""
        # TODO: Use actual Slack SDK
        # For now, return mock message ID
        return f"mock-{int(time.time())}"


class SendEmailAction(ActionBlock):
    """Send email."""

    action_type: ClassVar[str] = "send_email"
    category: ClassVar[ActionCategory] = ActionCategory.INTEGRATION
    display_name: ClassVar[str] = "Send Email"
    description: ClassVar[str] = "Send an email"
    icon: ClassVar[str] = "mail"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["to"],
        properties={
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "cc": {
                "type": "string",
                "description": "CC recipients (comma-separated)",
            },
            "bcc": {
                "type": "string",
                "description": "BCC recipients (comma-separated)",
            },
            "subject_template": {
                "type": "string",
                "description": "Subject line template",
            },
            "body_template": {
                "type": "string",
                "description": "Email body template",
            },
            "is_html": {
                "type": "boolean",
                "default": False,
                "description": "Whether body is HTML",
            },
            "reply_to": {
                "type": "string",
                "description": "Reply-to address",
            },
        },
    )

    def get_required_connectors(self) -> list[str]:
        """Requires email connector."""
        return ["email"]

    async def execute(self, context: ActionContext) -> ActionResult:
        """Send email."""
        start_time = time.time()

        try:
            to = self.config.get("to")
            cc = self.config.get("cc", "")
            bcc = self.config.get("bcc", "")
            subject_template = self.config.get("subject_template", "Notification")
            body_template = self.config.get("body_template", "{{summary}}")
            is_html = self.config.get("is_html", False)
            reply_to = self.config.get("reply_to")

            # Render templates
            subject = self._render_template(subject_template, context)
            body = self._render_template(body_template, context)

            # Send email
            message_id = await self._send_email(
                to=to,
                cc=cc,
                bcc=bcc,
                subject=subject,
                body=body,
                is_html=is_html,
                reply_to=reply_to,
            )

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Email sent",
                to=to,
                message_id=message_id,
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={
                    "message_id": message_id,
                    "to": to,
                    "subject": subject,
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Email send failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _render_template(self, template: str, context: ActionContext) -> str:
        """Render template with context variables."""
        import re

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and var_name in output:
                    return str(output[var_name])
            if var_name in context.variables:
                return str(context.variables[var_name])
            if var_name in context.trigger_data:
                return str(context.trigger_data[var_name])
            return f"{{{{{var_name}}}}}"

        return re.sub(r"\{\{(\w+)\}\}", replace_var, template)

    async def _send_email(
        self,
        to: str,
        cc: str,
        bcc: str,
        subject: str,
        body: str,
        is_html: bool,
        reply_to: str | None,
    ) -> str:
        """Send email via email service."""
        # TODO: Integrate with email service
        return f"email-{int(time.time())}"


class CreateTicketAction(ActionBlock):
    """Create ticket in issue tracker."""

    action_type: ClassVar[str] = "create_ticket"
    category: ClassVar[ActionCategory] = ActionCategory.INTEGRATION
    display_name: ClassVar[str] = "Create Ticket"
    description: ClassVar[str] = "Create a ticket in Jira, Linear, or other tracker"
    icon: ClassVar[str] = "clipboard"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["project", "title_template"],
        properties={
            "tracker": {
                "type": "string",
                "enum": ["jira", "linear", "github", "asana"],
                "default": "jira",
                "description": "Issue tracker to use",
            },
            "project": {
                "type": "string",
                "description": "Project key or ID",
            },
            "issue_type": {
                "type": "string",
                "enum": ["task", "bug", "story", "epic"],
                "default": "task",
                "description": "Type of issue to create",
            },
            "title_template": {
                "type": "string",
                "description": "Issue title template",
            },
            "description_template": {
                "type": "string",
                "description": "Issue description template",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "default": "medium",
                "description": "Issue priority",
            },
            "assignee": {
                "type": "string",
                "description": "Assignee user ID or email",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels to apply",
            },
        },
    )

    def get_required_connectors(self) -> list[str]:
        """Requires the configured tracker connector."""
        tracker = self.config.get("tracker", "jira")
        return [tracker]

    async def execute(self, context: ActionContext) -> ActionResult:
        """Create ticket."""
        start_time = time.time()

        try:
            tracker = self.config.get("tracker", "jira")
            project = self.config.get("project")
            issue_type = self.config.get("issue_type", "task")
            title_template = self.config.get("title_template", "{{title}}")
            description_template = self.config.get("description_template", "{{summary}}")
            priority = self.config.get("priority", "medium")
            assignee = self.config.get("assignee")
            labels = self.config.get("labels", [])

            # Render templates
            title = self._render_template(title_template, context)
            description = self._render_template(description_template, context)

            # Create ticket
            ticket_id = await self._create_ticket(
                tracker=tracker,
                project=project,
                issue_type=issue_type,
                title=title,
                description=description,
                priority=priority,
                assignee=assignee,
                labels=labels,
            )

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Ticket created",
                tracker=tracker,
                project=project,
                ticket_id=ticket_id,
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={
                    "ticket_id": ticket_id,
                    "tracker": tracker,
                    "project": project,
                    "url": f"https://{tracker}.example.com/{project}/{ticket_id}",
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Ticket creation failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _render_template(self, template: str, context: ActionContext) -> str:
        """Render template."""
        import re

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and var_name in output:
                    return str(output[var_name])
            if var_name in context.variables:
                return str(context.variables[var_name])
            if var_name in context.trigger_data:
                return str(context.trigger_data[var_name])
            return f"{{{{{var_name}}}}}"

        return re.sub(r"\{\{(\w+)\}\}", replace_var, template)

    async def _create_ticket(
        self,
        tracker: str,
        project: str,
        issue_type: str,
        title: str,
        description: str,
        priority: str,
        assignee: str | None,
        labels: list[str],
    ) -> str:
        """Create ticket in tracker."""
        # TODO: Integrate with actual tracker APIs
        return f"{project}-{int(time.time()) % 1000}"


class WebhookAction(ActionBlock):
    """Send webhook request."""

    action_type: ClassVar[str] = "webhook"
    category: ClassVar[ActionCategory] = ActionCategory.INTEGRATION
    display_name: ClassVar[str] = "Webhook"
    description: ClassVar[str] = "Send HTTP webhook request"
    icon: ClassVar[str] = "zap"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["url"],
        properties={
            "url": {
                "type": "string",
                "description": "Webhook URL",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "default": "POST",
                "description": "HTTP method",
            },
            "headers": {
                "type": "object",
                "description": "Custom headers",
            },
            "body_template": {
                "type": "string",
                "description": "Request body template (JSON)",
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "Request timeout in seconds",
            },
            "retry_count": {
                "type": "integer",
                "default": 3,
                "description": "Number of retries on failure",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Send webhook request."""
        start_time = time.time()

        try:
            url = self.config.get("url")
            method = self.config.get("method", "POST")
            headers = self.config.get("headers", {})
            body_template = self.config.get("body_template")
            timeout = self.config.get("timeout", 30)
            retry_count = self.config.get("retry_count", 3)

            # Prepare body
            if body_template:
                body = self._render_template(body_template, context)
            else:
                # Default: send all previous outputs
                body = {
                    "trigger": context.trigger_data,
                    "outputs": context.previous_outputs,
                    "variables": context.variables,
                }

            # Send request
            response = await self._send_request(
                url=url,
                method=method,
                headers=headers,
                body=body,
                timeout=timeout,
                retry_count=retry_count,
            )

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Webhook sent",
                url=url,
                method=method,
                status_code=response.get("status_code"),
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output=response,
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Webhook failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _render_template(self, template: str, context: ActionContext) -> Any:
        """Render JSON template."""
        import json
        import re

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and var_name in output:
                    value = output[var_name]
                    return json.dumps(value) if not isinstance(value, str) else value
            if var_name in context.variables:
                value = context.variables[var_name]
                return json.dumps(value) if not isinstance(value, str) else value
            if var_name in context.trigger_data:
                value = context.trigger_data[var_name]
                return json.dumps(value) if not isinstance(value, str) else value
            return f"{{{{{var_name}}}}}"

        rendered = re.sub(r"\{\{(\w+)\}\}", replace_var, template)
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            return rendered

    async def _send_request(
        self,
        url: str,
        method: str,
        headers: dict,
        body: Any,
        timeout: int,
        retry_count: int,
    ) -> dict[str, Any]:
        """Send HTTP request."""
        import aiohttp
        import json

        last_error = None
        for attempt in range(retry_count + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        headers={
                            "Content-Type": "application/json",
                            **headers,
                        },
                        json=body if isinstance(body, (dict, list)) else None,
                        data=body if isinstance(body, str) else None,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as response:
                        response_body = await response.text()
                        try:
                            response_json = json.loads(response_body)
                        except json.JSONDecodeError:
                            response_json = None

                        return {
                            "status_code": response.status,
                            "body": response_json or response_body,
                            "headers": dict(response.headers),
                        }
            except Exception as e:
                last_error = e
                self._logger.warning(
                    "Webhook attempt failed",
                    attempt=attempt + 1,
                    error=str(e),
                )

        raise last_error or Exception("Webhook failed after all retries")
