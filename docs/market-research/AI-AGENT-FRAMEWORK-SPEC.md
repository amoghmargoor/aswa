# ASWA AI Agent Framework - Technical Specification

## Overview

The AI Agent Framework enables ASWA to autonomously convert extracted insights into actions across enterprise systems. This document provides implementation specifications for Phase 9.

---

## Architecture

```
                                 ┌─────────────────────────────────┐
                                 │         Agent Registry          │
                                 │   (Available Agent Definitions) │
                                 └──────────────┬──────────────────┘
                                                │
┌─────────────────────┐         ┌───────────────▼───────────────────┐
│   Insight Stream    │────────►│        Agent Orchestrator         │
│   (From Phase 3)    │         │                                   │
└─────────────────────┘         │  • Matches insights to agents     │
                                │  • Manages execution pipeline     │
                                │  • Handles failures & retries     │
                                └───────────────┬───────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
         ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
         │  Summarizer      │       │  Jira Creator    │       │  Thread Creator  │
         │  Agent           │       │  Agent           │       │  Agent           │
         └────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
                  │                          │                          │
                  ▼                          ▼                          ▼
         ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
         │  Approval        │       │  Approval        │       │  Approval        │
         │  Gateway         │◄──────│  Gateway         │──────►│  Gateway         │
         └────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
                  │                          │                          │
                  ▼                          ▼                          ▼
         ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
         │  Notion/Confl.   │       │  Jira API        │       │  Slack/Teams     │
         │  Writer          │       │  Client          │       │  API             │
         └──────────────────┘       └──────────────────┘       └──────────────────┘
```

---

## Core Components

### 1. Agent Base Classes

**File:** `services/agent-service/src/aswa_agents/core/base.py`

```python
"""Base classes for ASWA AI Agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel


class ActionType(str, Enum):
    """Types of actions agents can take."""
    CREATE_TICKET = "create_ticket"
    UPDATE_TICKET = "update_ticket"
    POST_MESSAGE = "post_message"
    CREATE_THREAD = "create_thread"
    CREATE_DOCUMENT = "create_document"
    UPDATE_DOCUMENT = "update_document"
    SEND_NOTIFICATION = "send_notification"
    SCHEDULE_MEETING = "schedule_meeting"
    CUSTOM = "custom"


class ActionStatus(str, Enum):
    """Status of an action."""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalLevel(str, Enum):
    """Approval requirements for actions."""
    AUTO = "auto"  # Execute immediately
    NOTIFY = "notify"  # Execute and notify
    APPROVE = "approve"  # Require explicit approval
    MANUAL = "manual"  # Never auto-execute


class ConfidenceLevel(str, Enum):
    """Agent confidence in proposed action."""
    HIGH = "high"  # > 0.9
    MEDIUM = "medium"  # 0.7 - 0.9
    LOW = "low"  # < 0.7


@dataclass
class Insight:
    """Represents an insight from document analysis."""
    id: UUID
    tenant_id: str
    type: str
    title: str
    summary: str
    confidence: float
    source_documents: list[str]
    entities: list[dict]
    metadata: dict
    created_at: datetime
    tags: list[str] = field(default_factory=list)


@dataclass
class ActionContext:
    """Context for action execution."""
    insight: Insight
    tenant_id: str
    user_id: str | None
    organization_settings: dict
    agent_config: dict
    execution_id: UUID = field(default_factory=uuid4)


class Action(BaseModel):
    """Represents a planned action."""
    id: UUID = field(default_factory=uuid4)
    type: ActionType
    target_system: str
    parameters: dict[str, Any]
    confidence: float
    reasoning: str
    requires_approval: ApprovalLevel
    estimated_impact: str
    rollback_possible: bool = True


class ActionResult(BaseModel):
    """Result of action execution."""
    action_id: UUID
    status: ActionStatus
    result_data: dict[str, Any] | None = None
    error_message: str | None = None
    executed_at: datetime | None = None
    execution_time_ms: int | None = None
    external_id: str | None = None  # ID in target system


T = TypeVar("T", bound=Action)


class Agent(ABC, Generic[T]):
    """Base class for all ASWA AI Agents."""

    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__
        self.version = "1.0.0"

    @property
    @abstractmethod
    def supported_insight_types(self) -> list[str]:
        """Return list of insight types this agent handles."""
        pass

    @property
    @abstractmethod
    def required_permissions(self) -> list[str]:
        """Return list of permissions required by this agent."""
        pass

    @abstractmethod
    async def should_trigger(self, insight: Insight, context: ActionContext) -> bool:
        """
        Determine if this agent should act on the given insight.

        Returns True if the agent can meaningfully act on this insight.
        """
        pass

    @abstractmethod
    async def plan_actions(
        self, insight: Insight, context: ActionContext
    ) -> list[T]:
        """
        Plan the actions to take for the given insight.

        This is the LLM-powered step that determines what actions to take.
        Actions are not executed yet - they go through approval workflow.
        """
        pass

    @abstractmethod
    async def execute(
        self, action: T, context: ActionContext
    ) -> ActionResult:
        """
        Execute a single approved action.

        Should be idempotent where possible.
        """
        pass

    async def validate_action(self, action: T, context: ActionContext) -> bool:
        """
        Validate an action before execution.

        Override to add custom validation logic.
        """
        return True

    async def on_success(
        self, action: T, result: ActionResult, context: ActionContext
    ) -> None:
        """Hook called after successful execution."""
        pass

    async def on_failure(
        self, action: T, result: ActionResult, context: ActionContext
    ) -> None:
        """Hook called after failed execution."""
        pass

    def get_approval_level(self, action: T, context: ActionContext) -> ApprovalLevel:
        """
        Determine approval level for an action.

        Default implementation uses confidence thresholds from config.
        """
        thresholds = context.organization_settings.get("approval_thresholds", {
            "auto": 0.95,
            "notify": 0.85,
            "approve": 0.7
        })

        if action.confidence >= thresholds["auto"]:
            return ApprovalLevel.AUTO
        elif action.confidence >= thresholds["notify"]:
            return ApprovalLevel.NOTIFY
        elif action.confidence >= thresholds["approve"]:
            return ApprovalLevel.APPROVE
        else:
            return ApprovalLevel.MANUAL
```

### 2. Agent Registry

**File:** `services/agent-service/src/aswa_agents/core/registry.py`

```python
"""Agent registry for discovering and managing agents."""

from typing import Type

from .base import Agent, Insight


class AgentRegistry:
    """Registry for managing available agents."""

    _instance = None
    _agents: dict[str, Type[Agent]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, agent_class: Type[Agent]) -> Type[Agent]:
        """Decorator to register an agent."""
        cls._agents[agent_class.__name__] = agent_class
        return agent_class

    @classmethod
    def get_agent(cls, name: str) -> Type[Agent] | None:
        """Get agent class by name."""
        return cls._agents.get(name)

    @classmethod
    def get_all_agents(cls) -> dict[str, Type[Agent]]:
        """Get all registered agents."""
        return cls._agents.copy()

    @classmethod
    def find_agents_for_insight(
        cls, insight: Insight, tenant_config: dict
    ) -> list[Type[Agent]]:
        """Find all agents that can handle the given insight."""
        matching = []
        enabled_agents = tenant_config.get("enabled_agents", list(cls._agents.keys()))

        for name, agent_class in cls._agents.items():
            if name not in enabled_agents:
                continue

            instance = agent_class(tenant_config.get(f"agent_{name}", {}))
            if insight.type in instance.supported_insight_types:
                matching.append(agent_class)

        return matching
```

### 3. Agent Orchestrator

**File:** `services/agent-service/src/aswa_agents/core/orchestrator.py`

```python
"""Orchestrates agent execution and approval workflows."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from .base import (
    Action,
    ActionContext,
    ActionResult,
    ActionStatus,
    Agent,
    ApprovalLevel,
    Insight,
)
from .registry import AgentRegistry
from ..approval.service import ApprovalService
from ..persistence.repository import ActionRepository


class AgentOrchestrator:
    """Orchestrates the execution of agents based on insights."""

    def __init__(
        self,
        approval_service: ApprovalService,
        action_repository: ActionRepository,
        notification_client: Any,
    ):
        self.approval_service = approval_service
        self.action_repository = action_repository
        self.notification_client = notification_client
        self.registry = AgentRegistry()

    async def process_insight(
        self,
        insight: Insight,
        tenant_config: dict,
        user_id: str | None = None,
    ) -> list[UUID]:
        """
        Process an insight through matching agents.

        Returns list of action IDs created.
        """
        context = ActionContext(
            insight=insight,
            tenant_id=insight.tenant_id,
            user_id=user_id,
            organization_settings=tenant_config,
            agent_config={},
        )

        # Find matching agents
        agent_classes = self.registry.find_agents_for_insight(insight, tenant_config)

        action_ids = []
        for agent_class in agent_classes:
            agent_config = tenant_config.get(f"agent_{agent_class.__name__}", {})
            agent = agent_class(agent_config)
            context.agent_config = agent_config

            # Check if agent should trigger
            if not await agent.should_trigger(insight, context):
                continue

            # Plan actions
            actions = await agent.plan_actions(insight, context)

            # Process each action
            for action in actions:
                action_id = await self._process_action(agent, action, context)
                action_ids.append(action_id)

        return action_ids

    async def _process_action(
        self,
        agent: Agent,
        action: Action,
        context: ActionContext,
    ) -> UUID:
        """Process a single action through the approval workflow."""

        # Determine approval level
        approval_level = agent.get_approval_level(action, context)
        action.requires_approval = approval_level

        # Persist the action
        await self.action_repository.save(
            action=action,
            agent_name=agent.name,
            context=context,
        )

        if approval_level == ApprovalLevel.AUTO:
            # Execute immediately
            await self._execute_action(agent, action, context)

        elif approval_level == ApprovalLevel.NOTIFY:
            # Execute and notify
            result = await self._execute_action(agent, action, context)
            await self._send_notification(action, result, context)

        elif approval_level == ApprovalLevel.APPROVE:
            # Request approval
            await self.approval_service.request_approval(
                action=action,
                context=context,
                agent_name=agent.name,
            )

        # MANUAL actions just get logged, no auto-execution

        return action.id

    async def _execute_action(
        self,
        agent: Agent,
        action: Action,
        context: ActionContext,
    ) -> ActionResult:
        """Execute an approved action."""

        await self.action_repository.update_status(
            action.id, ActionStatus.EXECUTING
        )

        start_time = datetime.utcnow()

        try:
            # Validate
            if not await agent.validate_action(action, context):
                raise ValueError("Action validation failed")

            # Execute
            result = await agent.execute(action, context)

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.execution_time_ms = int(execution_time)

            # Update status
            await self.action_repository.update_result(action.id, result)

            # Call success hook
            await agent.on_success(action, result, context)

            return result

        except Exception as e:
            result = ActionResult(
                action_id=action.id,
                status=ActionStatus.FAILED,
                error_message=str(e),
            )
            await self.action_repository.update_result(action.id, result)
            await agent.on_failure(action, result, context)
            return result

    async def execute_approved_action(self, action_id: UUID) -> ActionResult:
        """Execute an action that has been approved."""
        action_record = await self.action_repository.get(action_id)
        if not action_record:
            raise ValueError(f"Action {action_id} not found")

        if action_record.status != ActionStatus.APPROVED:
            raise ValueError(f"Action {action_id} is not approved")

        agent_class = self.registry.get_agent(action_record.agent_name)
        if not agent_class:
            raise ValueError(f"Agent {action_record.agent_name} not found")

        agent = agent_class(action_record.context.agent_config)
        return await self._execute_action(
            agent, action_record.action, action_record.context
        )

    async def _send_notification(
        self,
        action: Action,
        result: ActionResult,
        context: ActionContext,
    ) -> None:
        """Send notification about executed action."""
        await self.notification_client.send(
            tenant_id=context.tenant_id,
            channel="slack",  # or from config
            message={
                "type": "action_executed",
                "action_type": action.type.value,
                "target": action.target_system,
                "status": result.status.value,
                "insight_title": context.insight.title,
            },
        )
```

### 4. Approval Service

**File:** `services/agent-service/src/aswa_agents/approval/service.py`

```python
"""Service for managing action approvals."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from ..core.base import Action, ActionContext, ActionStatus, ApprovalLevel


class ApprovalRequest:
    """Represents a pending approval request."""

    def __init__(
        self,
        action: Action,
        context: ActionContext,
        agent_name: str,
        expires_at: datetime | None = None,
    ):
        self.id = action.id
        self.action = action
        self.context = context
        self.agent_name = agent_name
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at or (self.created_at + timedelta(hours=24))
        self.status = ActionStatus.AWAITING_APPROVAL
        self.reviewed_by: str | None = None
        self.reviewed_at: datetime | None = None
        self.rejection_reason: str | None = None


class ApprovalService:
    """Manages approval workflows for agent actions."""

    def __init__(
        self,
        approval_repository: Any,
        notification_client: Any,
        slack_client: Any,
    ):
        self.approval_repository = approval_repository
        self.notification_client = notification_client
        self.slack_client = slack_client

    async def request_approval(
        self,
        action: Action,
        context: ActionContext,
        agent_name: str,
    ) -> ApprovalRequest:
        """Create an approval request and notify approvers."""

        request = ApprovalRequest(
            action=action,
            context=context,
            agent_name=agent_name,
        )

        # Persist request
        await self.approval_repository.save(request)

        # Determine approvers
        approvers = await self._get_approvers(context)

        # Send approval request via Slack
        message = self._build_approval_message(request)
        for approver in approvers:
            await self.slack_client.send_approval_request(
                user_id=approver,
                request_id=request.id,
                message=message,
            )

        return request

    async def approve(
        self,
        request_id: UUID,
        approver_id: str,
        modifications: dict | None = None,
    ) -> ApprovalRequest:
        """Approve an action request."""

        request = await self.approval_repository.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != ActionStatus.AWAITING_APPROVAL:
            raise ValueError(f"Request {request_id} is not pending approval")

        if request.expires_at < datetime.utcnow():
            raise ValueError(f"Request {request_id} has expired")

        # Apply modifications if provided
        if modifications:
            request.action.parameters.update(modifications)

        request.status = ActionStatus.APPROVED
        request.reviewed_by = approver_id
        request.reviewed_at = datetime.utcnow()

        await self.approval_repository.update(request)

        return request

    async def reject(
        self,
        request_id: UUID,
        approver_id: str,
        reason: str,
    ) -> ApprovalRequest:
        """Reject an action request."""

        request = await self.approval_repository.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        request.status = ActionStatus.REJECTED
        request.reviewed_by = approver_id
        request.reviewed_at = datetime.utcnow()
        request.rejection_reason = reason

        await self.approval_repository.update(request)

        return request

    async def _get_approvers(self, context: ActionContext) -> list[str]:
        """Determine who should approve this action."""

        settings = context.organization_settings

        # Default approvers from config
        approvers = settings.get("default_approvers", [])

        # Add action-type specific approvers
        action_type = context.insight.type
        type_approvers = settings.get("approvers_by_type", {}).get(action_type, [])
        approvers.extend(type_approvers)

        # Add the user who triggered the insight if available
        if context.user_id:
            approvers.append(context.user_id)

        return list(set(approvers))

    def _build_approval_message(self, request: ApprovalRequest) -> dict:
        """Build Slack message for approval request."""

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Action Approval Required: {request.action.type.value}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Agent:* {request.agent_name}\n"
                               f"*Target:* {request.action.target_system}\n"
                               f"*Confidence:* {request.action.confidence:.0%}\n"
                               f"*Insight:* {request.context.insight.title}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Reasoning:*\n{request.action.reasoning}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Estimated Impact:*\n{request.action.estimated_impact}",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": f"approve_{request.id}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject"},
                            "style": "danger",
                            "action_id": f"reject_{request.id}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Details"},
                            "action_id": f"details_{request.id}",
                        },
                    ],
                },
            ],
        }
```

---

## Agent Implementations

### 5. Jira Creator Agent

**File:** `services/agent-service/src/aswa_agents/agents/jira_creator.py`

```python
"""Agent that creates Jira tickets from insights."""

from typing import Any

from ..core.base import (
    Action,
    ActionContext,
    ActionResult,
    ActionStatus,
    ActionType,
    Agent,
    Insight,
)
from ..core.registry import AgentRegistry
from ..llm.client import LLMClient


class JiraTicketAction(Action):
    """Action to create a Jira ticket."""

    type: ActionType = ActionType.CREATE_TICKET
    target_system: str = "jira"

    # Jira-specific fields
    project_key: str
    issue_type: str
    summary: str
    description: str
    priority: str
    labels: list[str]
    assignee: str | None = None
    components: list[str] | None = None


@AgentRegistry.register
class JiraCreatorAgent(Agent[JiraTicketAction]):
    """Creates Jira tickets from actionable insights."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.llm_client = LLMClient()
        self.jira_client = None  # Injected
        self.entity_graph = None  # Injected

    @property
    def supported_insight_types(self) -> list[str]:
        return [
            "ACTION_ITEM",
            "BUG_REPORT",
            "FEATURE_REQUEST",
            "IMPROVEMENT",
            "RISK",
            "DECISION_REQUIRED",
        ]

    @property
    def required_permissions(self) -> list[str]:
        return ["jira:write", "jira:create_issue"]

    async def should_trigger(self, insight: Insight, context: ActionContext) -> bool:
        """Determine if we should create a Jira ticket for this insight."""

        # Check minimum confidence
        if insight.confidence < self.config.get("min_confidence", 0.7):
            return False

        # Check if Jira integration is enabled for tenant
        if not context.organization_settings.get("jira_enabled", False):
            return False

        # Check if insight type mapping exists
        type_mapping = self.config.get("insight_type_to_issue_type", {})
        if insight.type not in type_mapping:
            return False

        return True

    async def plan_actions(
        self, insight: Insight, context: ActionContext
    ) -> list[JiraTicketAction]:
        """Use LLM to plan Jira ticket creation."""

        # Get project mapping
        project_key = await self._determine_project(insight, context)
        issue_type = self.config["insight_type_to_issue_type"][insight.type]

        # Use LLM to generate ticket content
        prompt = self._build_ticket_prompt(insight, context)
        ticket_content = await self.llm_client.generate_structured(
            prompt=prompt,
            schema={
                "summary": "string, max 100 chars",
                "description": "string, Jira markdown format",
                "priority": "string, one of: Highest, High, Medium, Low, Lowest",
                "labels": "array of strings",
                "components": "array of strings or null",
            },
        )

        # Determine assignee using entity graph
        assignee = await self._find_best_assignee(insight, context)

        action = JiraTicketAction(
            project_key=project_key,
            issue_type=issue_type,
            summary=ticket_content["summary"],
            description=self._format_description(
                ticket_content["description"],
                insight,
            ),
            priority=ticket_content["priority"],
            labels=["aswa-generated"] + ticket_content["labels"],
            assignee=assignee,
            components=ticket_content.get("components"),
            confidence=insight.confidence,
            reasoning=f"Insight '{insight.title}' identified as {insight.type} "
                     f"with {insight.confidence:.0%} confidence",
            estimated_impact=f"Creates {issue_type} in {project_key}",
            parameters={
                "insight_id": str(insight.id),
                "source_documents": insight.source_documents,
            },
        )

        return [action]

    async def execute(
        self, action: JiraTicketAction, context: ActionContext
    ) -> ActionResult:
        """Create the Jira ticket."""

        try:
            issue = await self.jira_client.create_issue(
                project=action.project_key,
                issue_type=action.issue_type,
                summary=action.summary,
                description=action.description,
                priority=action.priority,
                labels=action.labels,
                assignee=action.assignee,
                components=action.components,
            )

            return ActionResult(
                action_id=action.id,
                status=ActionStatus.COMPLETED,
                result_data={
                    "issue_key": issue.key,
                    "issue_url": issue.url,
                },
                external_id=issue.key,
            )

        except Exception as e:
            return ActionResult(
                action_id=action.id,
                status=ActionStatus.FAILED,
                error_message=str(e),
            )

    async def _determine_project(
        self, insight: Insight, context: ActionContext
    ) -> str:
        """Determine the Jira project for this insight."""

        # Check explicit mapping in config
        project_mapping = self.config.get("project_mapping", {})

        # Try to match by entity
        for entity in insight.entities:
            if entity.get("type") == "TEAM":
                team_name = entity.get("name")
                if team_name in project_mapping:
                    return project_mapping[team_name]

        # Try to match by tag
        for tag in insight.tags:
            if tag in project_mapping:
                return project_mapping[tag]

        # Default project
        return self.config.get("default_project", "ASWA")

    async def _find_best_assignee(
        self, insight: Insight, context: ActionContext
    ) -> str | None:
        """Find the best assignee using entity graph."""

        if not self.entity_graph:
            return None

        # Look for person entities in the insight
        for entity in insight.entities:
            if entity.get("type") == "PERSON" and entity.get("role") == "owner":
                return entity.get("jira_user_id")

        # Use entity graph to find expert
        domain_tags = [t for t in insight.tags if not t.startswith("aswa-")]
        if domain_tags:
            expert = await self.entity_graph.find_expert(
                domain=domain_tags[0],
                tenant_id=context.tenant_id,
            )
            if expert:
                return expert.jira_user_id

        return None

    def _build_ticket_prompt(self, insight: Insight, context: ActionContext) -> str:
        """Build prompt for LLM ticket generation."""

        return f"""Generate a Jira ticket for the following insight.

Insight Type: {insight.type}
Title: {insight.title}
Summary: {insight.summary}

Source Documents:
{chr(10).join(f'- {doc}' for doc in insight.source_documents[:5])}

Related Entities:
{chr(10).join(f'- {e.get("type")}: {e.get("name")}' for e in insight.entities[:10])}

Tags: {', '.join(insight.tags)}

Generate a professional Jira ticket with:
1. A concise summary (max 100 characters)
2. A detailed description in Jira markdown format
3. Appropriate priority (Highest, High, Medium, Low, Lowest)
4. Relevant labels (2-4 labels)
5. Component suggestions if applicable

The description should include:
- Context and background
- Specific details from the insight
- Acceptance criteria or expected outcome
- Links to source documents
"""

    def _format_description(self, description: str, insight: Insight) -> str:
        """Format the description with ASWA metadata."""

        source_links = "\n".join(
            f"* [{doc}|{doc}]" for doc in insight.source_documents[:5]
        )

        return f"""{description}

----
h3. ASWA Metadata

*Generated by:* ASWA AI Agent
*Insight ID:* {insight.id}
*Confidence:* {insight.confidence:.0%}
*Created:* {insight.created_at.isoformat()}

h4. Source Documents
{source_links}
"""
```

### 6. Document Summarizer Agent

**File:** `services/agent-service/src/aswa_agents/agents/summarizer.py`

```python
"""Agent that creates document summaries."""

from ..core.base import (
    Action,
    ActionContext,
    ActionResult,
    ActionStatus,
    ActionType,
    Agent,
    Insight,
)
from ..core.registry import AgentRegistry
from ..llm.client import LLMClient


class DocumentSummaryAction(Action):
    """Action to create and post a document summary."""

    type: ActionType = ActionType.CREATE_DOCUMENT

    # Summary-specific fields
    summary_type: str  # "executive", "technical", "brief"
    content: str
    target_channel: str | None = None
    target_page_id: str | None = None


@AgentRegistry.register
class DocumentSummarizerAgent(Agent[DocumentSummaryAction]):
    """Creates summaries from newly ingested documents."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.llm_client = LLMClient()
        self.slack_client = None
        self.confluence_client = None

    @property
    def supported_insight_types(self) -> list[str]:
        return ["DOCUMENT_INGESTED", "DOCUMENT_UPDATED"]

    @property
    def required_permissions(self) -> list[str]:
        return ["slack:write", "confluence:write"]

    async def should_trigger(self, insight: Insight, context: ActionContext) -> bool:
        """Check if document should be summarized."""

        # Check if auto-summarization is enabled
        if not context.organization_settings.get("auto_summarize", False):
            return False

        # Check document type whitelist
        doc_types = self.config.get("summarize_doc_types", [
            "pdf", "docx", "confluence", "notion"
        ])
        doc_type = insight.metadata.get("document_type", "")
        if doc_type.lower() not in doc_types:
            return False

        # Check minimum length
        min_length = self.config.get("min_doc_length", 1000)
        if insight.metadata.get("char_count", 0) < min_length:
            return False

        return True

    async def plan_actions(
        self, insight: Insight, context: ActionContext
    ) -> list[DocumentSummaryAction]:
        """Plan summary creation and distribution."""

        actions = []

        # Determine summary types needed
        summary_types = self.config.get("summary_types", ["executive"])

        for summary_type in summary_types:
            # Generate summary
            summary_content = await self._generate_summary(
                insight, summary_type, context
            )

            # Determine distribution channels
            channels = self._get_distribution_channels(insight, context)

            for channel in channels:
                action = DocumentSummaryAction(
                    target_system=channel["type"],
                    summary_type=summary_type,
                    content=summary_content,
                    target_channel=channel.get("channel"),
                    target_page_id=channel.get("page_id"),
                    confidence=0.95,  # Summaries are high confidence
                    reasoning=f"Auto-summary for {insight.metadata.get('document_name')}",
                    estimated_impact=f"Post {summary_type} summary to {channel['type']}",
                    parameters={
                        "document_id": insight.source_documents[0],
                        "summary_type": summary_type,
                    },
                )
                actions.append(action)

        return actions

    async def execute(
        self, action: DocumentSummaryAction, context: ActionContext
    ) -> ActionResult:
        """Post the summary to target system."""

        try:
            if action.target_system == "slack":
                result = await self.slack_client.post_message(
                    channel=action.target_channel,
                    text=action.content,
                    blocks=self._format_slack_summary(action, context),
                )
                external_id = result["ts"]

            elif action.target_system == "confluence":
                result = await self.confluence_client.create_page(
                    parent_id=action.target_page_id,
                    title=f"Summary: {context.insight.metadata.get('document_name')}",
                    content=self._format_confluence_summary(action, context),
                )
                external_id = result["id"]

            else:
                raise ValueError(f"Unknown target system: {action.target_system}")

            return ActionResult(
                action_id=action.id,
                status=ActionStatus.COMPLETED,
                result_data={"posted_to": action.target_system},
                external_id=external_id,
            )

        except Exception as e:
            return ActionResult(
                action_id=action.id,
                status=ActionStatus.FAILED,
                error_message=str(e),
            )

    async def _generate_summary(
        self,
        insight: Insight,
        summary_type: str,
        context: ActionContext,
    ) -> str:
        """Generate summary using LLM."""

        prompts = {
            "executive": """Create an executive summary of this document.
Focus on: key decisions, action items, risks, and strategic implications.
Length: 3-5 bullet points, each 1-2 sentences.""",

            "technical": """Create a technical summary of this document.
Focus on: architecture decisions, technical requirements, implementation details.
Length: 5-7 bullet points with technical specifics.""",

            "brief": """Create a brief summary of this document.
Length: 2-3 sentences covering the main point.""",
        }

        prompt = f"""{prompts.get(summary_type, prompts["brief"])}

Document: {insight.metadata.get('document_name')}
Content Summary: {insight.summary}

Key Entities:
{chr(10).join(f'- {e.get("type")}: {e.get("name")}' for e in insight.entities[:5])}
"""

        return await self.llm_client.generate(prompt)

    def _get_distribution_channels(
        self, insight: Insight, context: ActionContext
    ) -> list[dict]:
        """Determine where to post the summary."""

        channels = []
        settings = context.organization_settings

        # Check for document-type specific channels
        doc_type = insight.metadata.get("document_type", "")
        type_channels = settings.get("summary_channels", {}).get(doc_type, [])
        channels.extend(type_channels)

        # Check for default channel
        if not channels and settings.get("default_summary_channel"):
            channels.append({
                "type": "slack",
                "channel": settings["default_summary_channel"],
            })

        return channels

    def _format_slack_summary(
        self, action: DocumentSummaryAction, context: ActionContext
    ) -> list[dict]:
        """Format summary for Slack."""

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Document Summary: {context.insight.metadata.get('document_name', 'Unknown')}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": action.content,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Summary type: {action.summary_type} | Generated by ASWA_",
                    },
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Document"},
                        "url": context.insight.source_documents[0],
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Ask Questions"},
                        "action_id": f"ask_about_{context.insight.id}",
                    },
                ],
            },
        ]

    def _format_confluence_summary(
        self, action: DocumentSummaryAction, context: ActionContext
    ) -> str:
        """Format summary for Confluence."""

        return f"""<ac:structured-macro ac:name="info">
<ac:rich-text-body>
<p>This summary was automatically generated by ASWA.</p>
</ac:rich-text-body>
</ac:structured-macro>

<h2>Summary</h2>
{action.content}

<h2>Source</h2>
<p>Document: {context.insight.metadata.get('document_name')}</p>
<p>Generated: {context.insight.created_at.isoformat()}</p>
"""
```

### 7. Thread Creator Agent

**File:** `services/agent-service/src/aswa_agents/agents/thread_creator.py`

```python
"""Agent that creates discussion threads from insights."""

from ..core.base import (
    Action,
    ActionContext,
    ActionResult,
    ActionStatus,
    ActionType,
    Agent,
    Insight,
)
from ..core.registry import AgentRegistry
from ..llm.client import LLMClient


class ThreadAction(Action):
    """Action to create a discussion thread."""

    type: ActionType = ActionType.CREATE_THREAD

    # Thread-specific fields
    platform: str  # "slack" or "teams"
    channel: str
    message: str
    mentions: list[str]
    thread_topic: str


@AgentRegistry.register
class ThreadCreatorAgent(Agent[ThreadAction]):
    """Creates discussion threads for insights requiring human input."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.llm_client = LLMClient()
        self.entity_graph = None

    @property
    def supported_insight_types(self) -> list[str]:
        return [
            "DECISION_REQUIRED",
            "CONFLICT_DETECTED",
            "QUESTION",
            "RISK",
            "STRATEGIC_OPPORTUNITY",
        ]

    @property
    def required_permissions(self) -> list[str]:
        return ["slack:write", "teams:write"]

    async def should_trigger(self, insight: Insight, context: ActionContext) -> bool:
        """Check if a discussion thread should be created."""

        if insight.confidence < self.config.get("min_confidence", 0.75):
            return False

        if not context.organization_settings.get("auto_threads", False):
            return False

        return True

    async def plan_actions(
        self, insight: Insight, context: ActionContext
    ) -> list[ThreadAction]:
        """Plan thread creation."""

        # Determine platform and channel
        platform = context.organization_settings.get("primary_platform", "slack")
        channel = await self._determine_channel(insight, context)

        # Find people to mention
        mentions = await self._find_relevant_people(insight, context)

        # Generate discussion prompt
        message = await self._generate_thread_message(insight, mentions, context)

        action = ThreadAction(
            target_system=platform,
            platform=platform,
            channel=channel,
            message=message,
            mentions=mentions,
            thread_topic=insight.title,
            confidence=insight.confidence,
            reasoning=f"Insight '{insight.title}' requires discussion",
            estimated_impact=f"Start thread in #{channel} with {len(mentions)} participants",
            parameters={"insight_id": str(insight.id)},
        )

        return [action]

    async def execute(
        self, action: ThreadAction, context: ActionContext
    ) -> ActionResult:
        """Create the discussion thread."""

        # Implementation would use Slack/Teams API
        # This is a placeholder structure

        return ActionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            result_data={
                "thread_id": "placeholder",
                "channel": action.channel,
                "participants": len(action.mentions),
            },
        )

    async def _determine_channel(
        self, insight: Insight, context: ActionContext
    ) -> str:
        """Determine the best channel for discussion."""

        channel_mapping = self.config.get("channel_mapping", {})

        # Try insight type mapping
        if insight.type in channel_mapping:
            return channel_mapping[insight.type]

        # Try tag-based mapping
        for tag in insight.tags:
            if tag in channel_mapping:
                return channel_mapping[tag]

        return self.config.get("default_channel", "general")

    async def _find_relevant_people(
        self, insight: Insight, context: ActionContext
    ) -> list[str]:
        """Find people to mention in the thread."""

        mentions = set()

        # Extract person entities from insight
        for entity in insight.entities:
            if entity.get("type") == "PERSON":
                slack_id = entity.get("slack_id")
                if slack_id:
                    mentions.add(slack_id)

        # Use entity graph to find experts
        if self.entity_graph:
            for tag in insight.tags[:3]:
                experts = await self.entity_graph.find_experts(
                    domain=tag,
                    tenant_id=context.tenant_id,
                    limit=2,
                )
                for expert in experts:
                    if expert.slack_id:
                        mentions.add(expert.slack_id)

        # Limit mentions to avoid spam
        return list(mentions)[:5]

    async def _generate_thread_message(
        self,
        insight: Insight,
        mentions: list[str],
        context: ActionContext,
    ) -> str:
        """Generate the thread-starting message."""

        mention_str = " ".join(f"<@{m}>" for m in mentions)

        prompt = f"""Generate a concise Slack message to start a discussion.

Topic: {insight.title}
Type: {insight.type}
Summary: {insight.summary}

Requirements:
- Start with the topic/question
- Briefly explain the context
- Ask a specific question or request input
- Keep it under 200 words
- Use Slack markdown
"""

        message = await self.llm_client.generate(prompt)
        return f"{mention_str}\n\n{message}"
```

---

## API Endpoints

### 8. Agent Service API

**File:** `services/agent-service/src/aswa_agents/api/routes.py`

```python
"""API routes for the agent service."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID

from ..core.orchestrator import AgentOrchestrator
from ..approval.service import ApprovalService


router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class InsightPayload(BaseModel):
    """Payload for processing an insight."""
    insight_id: UUID
    insight_type: str
    tenant_id: str
    user_id: str | None = None


class ApprovalPayload(BaseModel):
    """Payload for approving/rejecting an action."""
    approver_id: str
    modifications: dict | None = None
    rejection_reason: str | None = None


@router.post("/process-insight")
async def process_insight(
    payload: InsightPayload,
    orchestrator: AgentOrchestrator = Depends(),
):
    """Process an insight through matching agents."""

    # Fetch full insight from insight service
    insight = await fetch_insight(payload.insight_id)

    # Get tenant config
    tenant_config = await fetch_tenant_config(payload.tenant_id)

    # Process through agents
    action_ids = await orchestrator.process_insight(
        insight=insight,
        tenant_config=tenant_config,
        user_id=payload.user_id,
    )

    return {"action_ids": [str(aid) for aid in action_ids]}


@router.post("/actions/{action_id}/approve")
async def approve_action(
    action_id: UUID,
    payload: ApprovalPayload,
    approval_service: ApprovalService = Depends(),
    orchestrator: AgentOrchestrator = Depends(),
):
    """Approve a pending action."""

    request = await approval_service.approve(
        request_id=action_id,
        approver_id=payload.approver_id,
        modifications=payload.modifications,
    )

    # Execute the approved action
    result = await orchestrator.execute_approved_action(action_id)

    return {
        "action_id": str(action_id),
        "status": result.status.value,
        "result": result.result_data,
    }


@router.post("/actions/{action_id}/reject")
async def reject_action(
    action_id: UUID,
    payload: ApprovalPayload,
    approval_service: ApprovalService = Depends(),
):
    """Reject a pending action."""

    if not payload.rejection_reason:
        raise HTTPException(400, "Rejection reason is required")

    request = await approval_service.reject(
        request_id=action_id,
        approver_id=payload.approver_id,
        reason=payload.rejection_reason,
    )

    return {
        "action_id": str(action_id),
        "status": "rejected",
        "reason": payload.rejection_reason,
    }


@router.get("/actions/{action_id}")
async def get_action(action_id: UUID):
    """Get action details."""
    # Implementation
    pass


@router.get("/actions/pending")
async def list_pending_actions(
    tenant_id: str,
    limit: int = 50,
):
    """List pending actions for a tenant."""
    # Implementation
    pass


@router.get("/registry")
async def list_agents():
    """List all registered agents."""
    from ..core.registry import AgentRegistry

    agents = []
    for name, agent_class in AgentRegistry.get_all_agents().items():
        instance = agent_class({})
        agents.append({
            "name": name,
            "version": instance.version,
            "supported_types": instance.supported_insight_types,
            "required_permissions": instance.required_permissions,
        })

    return {"agents": agents}
```

---

## Configuration

### 9. Tenant Agent Configuration Schema

```yaml
# Example tenant configuration for agents
agents:
  enabled: true

  # Global settings
  default_approvers:
    - "@admin"
    - "@operations"

  approval_thresholds:
    auto: 0.95      # Auto-execute above this confidence
    notify: 0.85    # Execute and notify between this and auto
    approve: 0.7    # Require approval between this and notify
    # Below 0.7: Manual only (suggestion mode)

  # Per-agent configuration
  JiraCreatorAgent:
    enabled: true
    min_confidence: 0.75
    default_project: "ENG"
    project_mapping:
      backend: "BACKEND"
      frontend: "FRONTEND"
      infrastructure: "INFRA"
    insight_type_to_issue_type:
      ACTION_ITEM: "Task"
      BUG_REPORT: "Bug"
      FEATURE_REQUEST: "Story"
      IMPROVEMENT: "Improvement"
      RISK: "Bug"
      DECISION_REQUIRED: "Task"

  DocumentSummarizerAgent:
    enabled: true
    summary_types:
      - executive
      - technical
    summarize_doc_types:
      - pdf
      - docx
      - confluence
    min_doc_length: 1000
    summary_channels:
      pdf:
        - type: slack
          channel: "#documents"
      confluence:
        - type: confluence
          page_id: "123456"

  ThreadCreatorAgent:
    enabled: true
    min_confidence: 0.8
    channel_mapping:
      DECISION_REQUIRED: "#leadership"
      RISK: "#risk-alerts"
      STRATEGIC_OPPORTUNITY: "#strategy"
    default_channel: "#general"
```

---

## Next Steps

1. **Phase 9.1**: Implement core agent framework (base classes, registry, orchestrator)
2. **Phase 9.2**: Implement initial agents (Jira, Summarizer, Thread)
3. **Phase 9.3**: Build approval workflow and UI
4. **Phase 9.4**: Add workflow automation studio
5. **Phase 9.5**: ROI analytics dashboard

This framework positions ASWA as the only enterprise document intelligence platform that truly bridges insights and actions.
