# Task 9.4.2: Integration Action Blocks

## Objective

Implement action blocks for external integrations including Slack messaging, email sending, and ticket creation in issue trackers (Jira, Linear).

## Prerequisites

- Task 9.4.1 completed (Core Action Blocks)
- Integration service available for OAuth and connector management

## Implementation

### Step 1: Slack Action Block

```python
# services/agent-service/src/aswa_agents/actions/integrations/slack.py
"""Slack integration action blocks."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus
from aswa_agents.integrations.slack_client import SlackClient


class SlackMessageType(str, Enum):
    """Type of Slack message."""

    TEXT = "text"
    BLOCKS = "blocks"
    ATTACHMENT = "attachment"


class SendSlackConfig(BaseModel):
    """Configuration for send Slack action."""

    channel: str = Field(..., description="Channel ID or name (e.g., #general)")
    message_template: str | None = None
    message_field: str = "message"  # Field to use if no template
    include_source: bool = True
    thread_ts: str | None = None  # Reply to thread
    message_type: SlackMessageType = SlackMessageType.TEXT
    blocks_template: list[dict] | None = None
    unfurl_links: bool = True
    mention_users: list[str] = Field(default_factory=list)


class SendSlackOutput(BaseModel):
    """Output from send Slack action."""

    channel: str
    message_ts: str
    permalink: str | None = None
    success: bool


class SendSlackAction(ActionBlock[SendSlackConfig, SendSlackOutput]):
    """
    Send a message to Slack.

    Supports text messages, block kit messages, and attachments.
    Can include context from trigger data and previous actions.
    """

    action_type = "send_slack"
    display_name = "Send Slack Message"
    description = "Send a message to a Slack channel"
    category = "integration"

    def __init__(self, action_id: str, config: SendSlackConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute Slack message send."""
        # Get Slack client for tenant
        try:
            slack = await self._get_slack_client(context.tenant_id)
        except Exception as e:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Failed to get Slack client: {str(e)}",
            )

        # Build message
        message = self._build_message(context)

        if not message and self.config.message_type == SlackMessageType.TEXT:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="No message content available",
            )

        try:
            # Resolve channel
            channel_id = await slack.resolve_channel(self.config.channel)

            # Send message based on type
            if self.config.message_type == SlackMessageType.BLOCKS:
                blocks = self._build_blocks(context)
                response = await slack.send_blocks(
                    channel=channel_id,
                    blocks=blocks,
                    text=message,  # Fallback text
                    thread_ts=self.config.thread_ts,
                )
            else:
                response = await slack.send_message(
                    channel=channel_id,
                    text=message,
                    thread_ts=self.config.thread_ts,
                    unfurl_links=self.config.unfurl_links,
                )

            output = SendSlackOutput(
                channel=channel_id,
                message_ts=response["ts"],
                permalink=response.get("permalink"),
                success=True,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except Exception as e:
            self._logger.error("Slack send failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Failed to send Slack message: {str(e)}",
            )

    async def _get_slack_client(self, tenant_id: str) -> SlackClient:
        """Get authenticated Slack client for tenant."""
        from aswa_agents.integrations.connector_manager import ConnectorManager

        manager = ConnectorManager()
        credentials = await manager.get_credentials(tenant_id, "slack")

        return SlackClient(token=credentials["access_token"])

    def _build_message(self, context: ActionContext) -> str:
        """Build message content."""
        # Use template if provided
        if self.config.message_template:
            return self._apply_template(self.config.message_template, context)

        # Get message from field
        message = None

        # Check previous outputs
        for output in context.previous_outputs.values():
            if isinstance(output, dict):
                if self.config.message_field in output:
                    message = str(output[self.config.message_field])
                    break
                if "summary" in output:
                    message = str(output["summary"])
                    break

        # Check trigger data
        if not message and self.config.message_field in context.trigger_data:
            message = str(context.trigger_data[self.config.message_field])

        # Add mentions
        if message and self.config.mention_users:
            mentions = " ".join(f"<@{u}>" for u in self.config.mention_users)
            message = f"{mentions}\n\n{message}"

        # Add source info
        if message and self.config.include_source:
            source = context.trigger_data.get("source", "")
            if source:
                message = f"{message}\n\n_Source: {source}_"

        return message or ""

    def _build_blocks(self, context: ActionContext) -> list[dict]:
        """Build Slack blocks."""
        if self.config.blocks_template:
            # Apply template variables to blocks
            import json
            blocks_json = json.dumps(self.config.blocks_template)
            blocks_json = self._apply_template(blocks_json, context)
            return json.loads(blocks_json)

        # Generate default blocks from content
        message = self._build_message(context)
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message[:3000],  # Slack limit
                }
            }
        ]

        # Add context block with source
        if self.config.include_source:
            source = context.trigger_data.get("source", "Agent")
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Sent by ASWA Agent | Source: {source}_"
                    }
                ]
            })

        return blocks

    def _apply_template(self, template: str, context: ActionContext) -> str:
        """Apply context variables to template."""
        result = template

        # Replace trigger data
        for key, value in context.trigger_data.items():
            result = result.replace(f"{{{{trigger.{key}}}}}", str(value))

        # Replace previous outputs
        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                for key, value in output.items():
                    result = result.replace(f"{{{{outputs.{action_id}.{key}}}}}", str(value))

        # Replace variables
        for key, value in context.variables.items():
            result = result.replace(f"{{{{vars.{key}}}}}", str(value))

        return result

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return SendSlackConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return SendSlackOutput.model_json_schema()
```

### Step 2: Email Action Block

```python
# services/agent-service/src/aswa_agents/actions/integrations/email.py
"""Email integration action blocks."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, EmailStr

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class EmailFormat(str, Enum):
    """Email body format."""

    PLAIN = "plain"
    HTML = "html"
    MARKDOWN = "markdown"


class SendEmailConfig(BaseModel):
    """Configuration for send email action."""

    to: list[str] = Field(..., min_length=1)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject_template: str | None = None
    subject_field: str = "subject"
    body_template: str | None = None
    body_field: str = "body"
    format: EmailFormat = EmailFormat.PLAIN
    reply_to: str | None = None
    include_attachments: bool = False
    from_name: str | None = None


class SendEmailOutput(BaseModel):
    """Output from send email action."""

    message_id: str
    to: list[str]
    subject: str
    success: bool


class SendEmailAction(ActionBlock[SendEmailConfig, SendEmailOutput]):
    """
    Send an email.

    Supports plain text, HTML, and Markdown formats.
    Can use templates with context variables.
    """

    action_type = "send_email"
    display_name = "Send Email"
    description = "Send an email to specified recipients"
    category = "integration"

    def __init__(self, action_id: str, config: SendEmailConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute email send."""
        # Build email content
        subject = self._build_subject(context)
        body = self._build_body(context)

        if not subject:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="No email subject available",
            )

        if not body:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="No email body available",
            )

        try:
            # Get email service
            email_service = await self._get_email_service(context.tenant_id)

            # Format body
            formatted_body = self._format_body(body)

            # Send email
            message_id = await email_service.send(
                to=self.config.to,
                cc=self.config.cc,
                bcc=self.config.bcc,
                subject=subject,
                body=formatted_body,
                is_html=self.config.format != EmailFormat.PLAIN,
                reply_to=self.config.reply_to,
                from_name=self.config.from_name,
            )

            output = SendEmailOutput(
                message_id=message_id,
                to=self.config.to,
                subject=subject,
                success=True,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except Exception as e:
            self._logger.error("Email send failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Failed to send email: {str(e)}",
            )

    async def _get_email_service(self, tenant_id: str):
        """Get email service for tenant."""
        from aswa_agents.integrations.email_service import EmailService

        return EmailService(tenant_id=tenant_id)

    def _build_subject(self, context: ActionContext) -> str:
        """Build email subject."""
        if self.config.subject_template:
            return self._apply_template(self.config.subject_template, context)

        # Get from context
        for output in context.previous_outputs.values():
            if isinstance(output, dict) and self.config.subject_field in output:
                return str(output[self.config.subject_field])

        if self.config.subject_field in context.trigger_data:
            return str(context.trigger_data[self.config.subject_field])

        # Generate from content
        if "subject" in context.trigger_data:
            return f"Re: {context.trigger_data['subject']}"

        return "Notification from ASWA Agent"

    def _build_body(self, context: ActionContext) -> str:
        """Build email body."""
        if self.config.body_template:
            return self._apply_template(self.config.body_template, context)

        # Get from context
        for output in context.previous_outputs.values():
            if isinstance(output, dict):
                if self.config.body_field in output:
                    return str(output[self.config.body_field])
                if "summary" in output:
                    return str(output["summary"])

        if self.config.body_field in context.trigger_data:
            return str(context.trigger_data[self.config.body_field])

        return ""

    def _format_body(self, body: str) -> str:
        """Format body based on format setting."""
        if self.config.format == EmailFormat.MARKDOWN:
            import markdown
            return markdown.markdown(body)
        elif self.config.format == EmailFormat.HTML:
            return body
        else:
            return body

    def _apply_template(self, template: str, context: ActionContext) -> str:
        """Apply context variables to template."""
        result = template

        for key, value in context.trigger_data.items():
            result = result.replace(f"{{{{trigger.{key}}}}}", str(value))

        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                for key, value in output.items():
                    result = result.replace(f"{{{{outputs.{action_id}.{key}}}}}", str(value))

        for key, value in context.variables.items():
            result = result.replace(f"{{{{vars.{key}}}}}", str(value))

        return result

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return SendEmailConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return SendEmailOutput.model_json_schema()
```

### Step 3: Ticket Creation Action Block

```python
# services/agent-service/src/aswa_agents/actions/integrations/ticket.py
"""Ticket/issue creation action blocks."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class TicketProvider(str, Enum):
    """Supported ticket providers."""

    JIRA = "jira"
    LINEAR = "linear"
    GITHUB = "github"
    ASANA = "asana"


class TicketPriority(str, Enum):
    """Ticket priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"


class CreateTicketConfig(BaseModel):
    """Configuration for create ticket action."""

    provider: TicketProvider
    project: str = Field(..., description="Project key/ID")
    issue_type: str = "Task"
    title_template: str | None = None
    title_field: str = "title"
    description_template: str | None = None
    description_field: str = "description"
    priority: TicketPriority = TicketPriority.MEDIUM
    labels: list[str] = Field(default_factory=list)
    assignee: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    include_source_link: bool = True


class CreateTicketOutput(BaseModel):
    """Output from create ticket action."""

    ticket_id: str
    ticket_key: str
    url: str
    provider: str
    success: bool


class CreateTicketAction(ActionBlock[CreateTicketConfig, CreateTicketOutput]):
    """
    Create a ticket in an issue tracker.

    Supports Jira, Linear, GitHub Issues, and Asana.
    """

    action_type = "create_ticket"
    display_name = "Create Ticket"
    description = "Create a ticket in an issue tracker"
    category = "integration"

    PRIORITY_MAPPING = {
        TicketProvider.JIRA: {
            TicketPriority.LOW: "Low",
            TicketPriority.MEDIUM: "Medium",
            TicketPriority.HIGH: "High",
            TicketPriority.CRITICAL: "Critical",
            TicketPriority.URGENT: "Highest",
        },
        TicketProvider.LINEAR: {
            TicketPriority.LOW: 4,
            TicketPriority.MEDIUM: 3,
            TicketPriority.HIGH: 2,
            TicketPriority.CRITICAL: 1,
            TicketPriority.URGENT: 0,
        },
    }

    def __init__(self, action_id: str, config: CreateTicketConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute ticket creation."""
        title = self._build_title(context)
        description = self._build_description(context)

        if not title:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="No ticket title available",
            )

        try:
            if self.config.provider == TicketProvider.JIRA:
                result = await self._create_jira_ticket(context, title, description)
            elif self.config.provider == TicketProvider.LINEAR:
                result = await self._create_linear_ticket(context, title, description)
            elif self.config.provider == TicketProvider.GITHUB:
                result = await self._create_github_issue(context, title, description)
            else:
                return ActionResult(
                    action_id=self.action_id,
                    status=ActionStatus.FAILED,
                    error=f"Unsupported provider: {self.config.provider}",
                )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=result.model_dump(),
            )

        except Exception as e:
            self._logger.error("Ticket creation failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Failed to create ticket: {str(e)}",
            )

    async def _create_jira_ticket(
        self, context: ActionContext, title: str, description: str
    ) -> CreateTicketOutput:
        """Create Jira ticket."""
        from aswa_agents.integrations.jira_client import JiraClient
        from aswa_agents.integrations.connector_manager import ConnectorManager

        manager = ConnectorManager()
        credentials = await manager.get_credentials(context.tenant_id, "jira")

        jira = JiraClient(
            base_url=credentials["base_url"],
            token=credentials["access_token"],
        )

        # Map priority
        priority = self.PRIORITY_MAPPING[TicketProvider.JIRA].get(
            self.config.priority, "Medium"
        )

        # Build fields
        fields = {
            "project": {"key": self.config.project},
            "summary": title,
            "description": description,
            "issuetype": {"name": self.config.issue_type},
            "priority": {"name": priority},
        }

        if self.config.assignee:
            fields["assignee"] = {"name": self.config.assignee}

        if self.config.labels:
            fields["labels"] = self.config.labels

        # Add custom fields
        fields.update(self.config.custom_fields)

        # Create issue
        issue = await jira.create_issue(fields)

        return CreateTicketOutput(
            ticket_id=issue["id"],
            ticket_key=issue["key"],
            url=f"{credentials['base_url']}/browse/{issue['key']}",
            provider="jira",
            success=True,
        )

    async def _create_linear_ticket(
        self, context: ActionContext, title: str, description: str
    ) -> CreateTicketOutput:
        """Create Linear ticket."""
        from aswa_agents.integrations.linear_client import LinearClient
        from aswa_agents.integrations.connector_manager import ConnectorManager

        manager = ConnectorManager()
        credentials = await manager.get_credentials(context.tenant_id, "linear")

        linear = LinearClient(token=credentials["access_token"])

        # Map priority
        priority = self.PRIORITY_MAPPING[TicketProvider.LINEAR].get(
            self.config.priority, 3
        )

        # Get team ID for project
        team = await linear.get_team_by_key(self.config.project)

        # Create issue
        issue = await linear.create_issue(
            team_id=team["id"],
            title=title,
            description=description,
            priority=priority,
            labels=self.config.labels,
            assignee=self.config.assignee,
        )

        return CreateTicketOutput(
            ticket_id=issue["id"],
            ticket_key=issue["identifier"],
            url=issue["url"],
            provider="linear",
            success=True,
        )

    async def _create_github_issue(
        self, context: ActionContext, title: str, description: str
    ) -> CreateTicketOutput:
        """Create GitHub issue."""
        from aswa_agents.integrations.github_client import GitHubClient
        from aswa_agents.integrations.connector_manager import ConnectorManager

        manager = ConnectorManager()
        credentials = await manager.get_credentials(context.tenant_id, "github")

        github = GitHubClient(token=credentials["access_token"])

        # Parse repo from project (format: owner/repo)
        owner, repo = self.config.project.split("/")

        # Create issue
        issue = await github.create_issue(
            owner=owner,
            repo=repo,
            title=title,
            body=description,
            labels=self.config.labels,
            assignees=[self.config.assignee] if self.config.assignee else [],
        )

        return CreateTicketOutput(
            ticket_id=str(issue["id"]),
            ticket_key=f"#{issue['number']}",
            url=issue["html_url"],
            provider="github",
            success=True,
        )

    def _build_title(self, context: ActionContext) -> str:
        """Build ticket title."""
        if self.config.title_template:
            return self._apply_template(self.config.title_template, context)

        for output in context.previous_outputs.values():
            if isinstance(output, dict) and self.config.title_field in output:
                return str(output[self.config.title_field])

        if self.config.title_field in context.trigger_data:
            return str(context.trigger_data[self.config.title_field])

        # Auto-generate from content
        if "subject" in context.trigger_data:
            return str(context.trigger_data["subject"])

        return "New issue from ASWA Agent"

    def _build_description(self, context: ActionContext) -> str:
        """Build ticket description."""
        if self.config.description_template:
            return self._apply_template(self.config.description_template, context)

        parts = []

        # Get main content
        for output in context.previous_outputs.values():
            if isinstance(output, dict):
                if self.config.description_field in output:
                    parts.append(str(output[self.config.description_field]))
                elif "summary" in output:
                    parts.append(str(output["summary"]))

        if not parts and self.config.description_field in context.trigger_data:
            parts.append(str(context.trigger_data[self.config.description_field]))

        # Add source link
        if self.config.include_source_link:
            source = context.trigger_data.get("source_url") or context.trigger_data.get("source")
            if source:
                parts.append(f"\n\n---\nSource: {source}")

        return "\n\n".join(parts) if parts else "Created by ASWA Agent"

    def _apply_template(self, template: str, context: ActionContext) -> str:
        """Apply context variables to template."""
        result = template

        for key, value in context.trigger_data.items():
            result = result.replace(f"{{{{trigger.{key}}}}}", str(value))

        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                for key, value in output.items():
                    result = result.replace(f"{{{{outputs.{action_id}.{key}}}}}", str(value))

        return result

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return CreateTicketConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return CreateTicketOutput.model_json_schema()
```

### Step 4: HTTP Request Action Block

```python
# services/agent-service/src/aswa_agents/actions/integrations/http_request.py
"""HTTP request action block for custom integrations."""

from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class HttpMethod(str, Enum):
    """HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class HttpRequestConfig(BaseModel):
    """Configuration for HTTP request action."""

    url: str
    method: HttpMethod = HttpMethod.POST
    headers: dict[str, str] = Field(default_factory=dict)
    body_template: str | None = None
    body_field: str | None = None
    json_body: dict[str, Any] | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    expected_status: list[int] = Field(default=[200, 201, 202, 204])
    extract_response_field: str | None = None
    include_auth: bool = False
    auth_header_name: str = "Authorization"


class HttpRequestOutput(BaseModel):
    """Output from HTTP request action."""

    status_code: int
    response_body: Any
    response_headers: dict[str, str]
    success: bool
    extracted_value: Any = None


class HttpRequestAction(ActionBlock[HttpRequestConfig, HttpRequestOutput]):
    """
    Make an HTTP request.

    Enables integration with any REST API.
    Supports templating for URL, headers, and body.
    """

    action_type = "http_request"
    display_name = "HTTP Request"
    description = "Make an HTTP request to an external API"
    category = "integration"

    def __init__(self, action_id: str, config: HttpRequestConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute HTTP request."""
        # Build request
        url = self._apply_template(self.config.url, context)
        headers = {k: self._apply_template(v, context) for k, v in self.config.headers.items()}
        body = self._build_body(context)

        # Add auth if configured
        if self.config.include_auth:
            auth_value = await self._get_auth_header(context)
            if auth_value:
                headers[self.config.auth_header_name] = auth_value

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                if self.config.method in [HttpMethod.GET, HttpMethod.DELETE]:
                    response = await client.request(
                        self.config.method.value,
                        url,
                        headers=headers,
                    )
                else:
                    if isinstance(body, dict):
                        response = await client.request(
                            self.config.method.value,
                            url,
                            headers=headers,
                            json=body,
                        )
                    else:
                        response = await client.request(
                            self.config.method.value,
                            url,
                            headers=headers,
                            content=body,
                        )

            # Parse response
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            # Check status
            success = response.status_code in self.config.expected_status

            # Extract value if configured
            extracted = None
            if self.config.extract_response_field and isinstance(response_body, dict):
                extracted = self._extract_field(response_body, self.config.extract_response_field)

            output = HttpRequestOutput(
                status_code=response.status_code,
                response_body=response_body,
                response_headers=dict(response.headers),
                success=success,
                extracted_value=extracted,
            )

            status = ActionStatus.COMPLETED if success else ActionStatus.FAILED

            return ActionResult(
                action_id=self.action_id,
                status=status,
                output=output.model_dump(),
                error=None if success else f"Unexpected status code: {response.status_code}",
            )

        except httpx.TimeoutException:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Request timed out after {self.config.timeout_seconds}s",
            )
        except Exception as e:
            self._logger.error("HTTP request failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"HTTP request failed: {str(e)}",
            )

    def _build_body(self, context: ActionContext) -> Any:
        """Build request body."""
        if self.config.json_body:
            # Apply templates to JSON body
            return self._apply_template_to_dict(self.config.json_body, context)

        if self.config.body_template:
            return self._apply_template(self.config.body_template, context)

        if self.config.body_field:
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and self.config.body_field in output:
                    return output[self.config.body_field]

            if self.config.body_field in context.trigger_data:
                return context.trigger_data[self.config.body_field]

        return None

    def _apply_template(self, template: str, context: ActionContext) -> str:
        """Apply context variables to template."""
        result = template

        for key, value in context.trigger_data.items():
            result = result.replace(f"{{{{trigger.{key}}}}}", str(value))

        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                for key, value in output.items():
                    result = result.replace(f"{{{{outputs.{action_id}.{key}}}}}", str(value))

        for key, value in context.variables.items():
            result = result.replace(f"{{{{vars.{key}}}}}", str(value))

        return result

    def _apply_template_to_dict(self, d: dict, context: ActionContext) -> dict:
        """Recursively apply templates to dict values."""
        result = {}
        for key, value in d.items():
            if isinstance(value, str):
                result[key] = self._apply_template(value, context)
            elif isinstance(value, dict):
                result[key] = self._apply_template_to_dict(value, context)
            elif isinstance(value, list):
                result[key] = [
                    self._apply_template(v, context) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def _extract_field(self, data: dict, field_path: str) -> Any:
        """Extract a nested field from response."""
        parts = field_path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return None

        return current

    async def _get_auth_header(self, context: ActionContext) -> str | None:
        """Get auth header value."""
        # Check for API key in variables
        api_key = context.variables.get("api_key")
        if api_key:
            return f"Bearer {api_key}"

        return None

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return HttpRequestConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return HttpRequestOutput.model_json_schema()
```

## Test Cases

```python
# services/agent-service/tests/unit/test_integration_actions.py
"""Tests for integration action blocks."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_agents.actions.base import ActionContext, ActionStatus
from aswa_agents.actions.integrations.slack import SendSlackAction, SendSlackConfig
from aswa_agents.actions.integrations.email import SendEmailAction, SendEmailConfig
from aswa_agents.actions.integrations.ticket import CreateTicketAction, CreateTicketConfig, TicketProvider
from aswa_agents.actions.integrations.http_request import HttpRequestAction, HttpRequestConfig, HttpMethod


@pytest.fixture
def context():
    """Create test context."""
    return ActionContext(
        execution_id=uuid4(),
        agent_id=uuid4(),
        tenant_id="test-tenant",
        trigger_data={
            "subject": "Test Subject",
            "content": "Test content for processing",
            "source": "email",
        },
        previous_outputs={
            "summarize": {
                "summary": "This is a summary of the content.",
            }
        },
    )


class TestSendSlackAction:
    """Test SendSlackAction."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, context):
        """Test successful Slack message send."""
        config = SendSlackConfig(
            channel="#general",
            message_template="New update: {{outputs.summarize.summary}}",
        )
        action = SendSlackAction("test-slack", config)

        mock_client = AsyncMock()
        mock_client.resolve_channel.return_value = "C123456"
        mock_client.send_message.return_value = {
            "ts": "1234567890.123456",
            "permalink": "https://slack.com/...",
        }

        with patch.object(action, "_get_slack_client", return_value=mock_client):
            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["success"] is True
            assert "message_ts" in result.output

    @pytest.mark.asyncio
    async def test_send_with_mentions(self, context):
        """Test Slack message with user mentions."""
        config = SendSlackConfig(
            channel="#alerts",
            message_field="summary",
            mention_users=["U123", "U456"],
        )
        action = SendSlackAction("test-slack", config)

        mock_client = AsyncMock()
        mock_client.resolve_channel.return_value = "C123"
        mock_client.send_message.return_value = {"ts": "123"}

        with patch.object(action, "_get_slack_client", return_value=mock_client):
            result = await action.execute(context)

            # Verify mentions in message
            call_args = mock_client.send_message.call_args
            message = call_args.kwargs.get("text") or call_args[1].get("text", "")
            assert "<@U123>" in message
            assert "<@U456>" in message


class TestSendEmailAction:
    """Test SendEmailAction."""

    @pytest.mark.asyncio
    async def test_send_email_success(self, context):
        """Test successful email send."""
        config = SendEmailConfig(
            to=["user@example.com"],
            subject_template="Update: {{trigger.subject}}",
            body_template="Summary:\n{{outputs.summarize.summary}}",
        )
        action = SendEmailAction("test-email", config)

        mock_service = AsyncMock()
        mock_service.send.return_value = "msg-12345"

        with patch.object(action, "_get_email_service", return_value=mock_service):
            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["success"] is True
            assert result.output["message_id"] == "msg-12345"

    @pytest.mark.asyncio
    async def test_email_with_multiple_recipients(self, context):
        """Test email with CC and BCC."""
        config = SendEmailConfig(
            to=["to@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        action = SendEmailAction("test-email", config)

        mock_service = AsyncMock()
        mock_service.send.return_value = "msg-123"

        with patch.object(action, "_get_email_service", return_value=mock_service):
            result = await action.execute(context)

            call_args = mock_service.send.call_args
            assert call_args.kwargs["to"] == ["to@example.com"]
            assert call_args.kwargs["cc"] == ["cc@example.com"]
            assert call_args.kwargs["bcc"] == ["bcc@example.com"]


class TestCreateTicketAction:
    """Test CreateTicketAction."""

    @pytest.mark.asyncio
    async def test_create_jira_ticket(self, context):
        """Test Jira ticket creation."""
        config = CreateTicketConfig(
            provider=TicketProvider.JIRA,
            project="PROJ",
            title_template="Issue: {{trigger.subject}}",
            description_template="{{outputs.summarize.summary}}",
            labels=["automated", "aswa"],
        )
        action = CreateTicketAction("test-ticket", config)

        with patch.object(action, "_create_jira_ticket", new_callable=AsyncMock) as mock:
            from aswa_agents.actions.integrations.ticket import CreateTicketOutput
            mock.return_value = CreateTicketOutput(
                ticket_id="12345",
                ticket_key="PROJ-123",
                url="https://jira.example.com/browse/PROJ-123",
                provider="jira",
                success=True,
            )

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["ticket_key"] == "PROJ-123"

    @pytest.mark.asyncio
    async def test_create_linear_ticket(self, context):
        """Test Linear ticket creation."""
        config = CreateTicketConfig(
            provider=TicketProvider.LINEAR,
            project="ENG",
        )
        action = CreateTicketAction("test-ticket", config)

        with patch.object(action, "_create_linear_ticket", new_callable=AsyncMock) as mock:
            from aswa_agents.actions.integrations.ticket import CreateTicketOutput
            mock.return_value = CreateTicketOutput(
                ticket_id="abc-123",
                ticket_key="ENG-42",
                url="https://linear.app/team/ENG-42",
                provider="linear",
                success=True,
            )

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["provider"] == "linear"


class TestHttpRequestAction:
    """Test HttpRequestAction."""

    @pytest.mark.asyncio
    async def test_post_request_success(self, context):
        """Test successful POST request."""
        config = HttpRequestConfig(
            url="https://api.example.com/webhook",
            method=HttpMethod.POST,
            json_body={"message": "{{outputs.summarize.summary}}"},
        )
        action = HttpRequestAction("test-http", config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_response.headers = {}

            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["status_code"] == 200

    @pytest.mark.asyncio
    async def test_request_timeout(self, context):
        """Test request timeout handling."""
        config = HttpRequestConfig(
            url="https://api.example.com/slow",
            timeout_seconds=5,
        )
        action = HttpRequestAction("test-http", config)

        import httpx
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await action.execute(context)

            assert result.status == ActionStatus.FAILED
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_extract_response_field(self, context):
        """Test extracting field from response."""
        config = HttpRequestConfig(
            url="https://api.example.com/data",
            method=HttpMethod.GET,
            extract_response_field="data.items.0.id",
        )
        action = HttpRequestAction("test-http", config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"items": [{"id": "extracted-id"}]}
            }
            mock_response.headers = {}

            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await action.execute(context)

            assert result.output["extracted_value"] == "extracted-id"
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_integration_actions.py -v
   ```

2. **Test with mock integrations:**
   ```python
   from aswa_agents.actions.integrations.slack import SendSlackAction, SendSlackConfig
   from aswa_agents.actions.base import ActionContext
   from uuid import uuid4

   config = SendSlackConfig(
       channel="#test",
       message_template="Hello from agent!",
   )
   action = SendSlackAction("test", config)

   context = ActionContext(
       execution_id=uuid4(),
       agent_id=uuid4(),
       tenant_id="test",
       trigger_data={"content": "Test"}
   )

   # With mocked Slack client
   result = await action.run(context)
   print(result)
   ```

3. **Verify template substitution:**
   ```python
   from aswa_agents.actions.integrations.ticket import CreateTicketAction, CreateTicketConfig, TicketProvider

   config = CreateTicketConfig(
       provider=TicketProvider.JIRA,
       project="TEST",
       title_template="[Agent] {{trigger.subject}}",
   )
   action = CreateTicketAction("test", config)

   title = action._build_title(context)
   print(f"Generated title: {title}")
   ```

## Next Task

Proceed to `task-9.4.3-logic-action-blocks.md` for implementing logic and control flow action blocks.
