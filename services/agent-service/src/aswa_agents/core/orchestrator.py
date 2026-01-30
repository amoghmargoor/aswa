"""Orchestrates agent execution and approval workflows."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from aswa_agents.config import get_settings
from aswa_agents.core.base import Agent
from aswa_agents.core.models import (
    Action,
    ActionContext,
    ActionResult,
    ExecutionResult,
    TriggerData,
)
from aswa_agents.core.registry import AgentRegistry
from aswa_agents.core.types import ActionStatus, ApprovalLevel
from aswa_agents.persistence.repository import ActionRepository, ExecutionRepository
from aswa_agents.approval.service import ApprovalService
from aswa_agents.utils.metrics import (
    AGENT_EXECUTIONS_TOTAL,
    AGENT_EXECUTION_DURATION,
    ACTION_EXECUTIONS_TOTAL,
)

logger = structlog.get_logger()


class ExecutionError(Exception):
    """Error during agent execution."""
    pass


class RetryableError(Exception):
    """Error that can be retried."""
    pass


class AgentOrchestrator:
    """
    Orchestrates the execution of agents based on triggers.

    The orchestrator:
    1. Matches triggers to appropriate agents
    2. Invokes agent planning to determine actions
    3. Routes actions through approval workflow
    4. Executes approved actions with retry logic
    5. Records execution results and metrics

    Usage:
        orchestrator = AgentOrchestrator(...)
        execution_ids = await orchestrator.process_trigger(trigger, tenant_config)
    """

    def __init__(
        self,
        action_repository: ActionRepository,
        execution_repository: ExecutionRepository,
        approval_service: ApprovalService,
        notification_client: Any = None,
    ):
        self.action_repository = action_repository
        self.execution_repository = execution_repository
        self.approval_service = approval_service
        self.notification_client = notification_client
        self.settings = get_settings()
        self._logger = logger.bind(component="orchestrator")

    async def process_trigger(
        self,
        trigger: TriggerData,
        tenant_config: dict,
        user_id: str | None = None,
        dry_run: bool = False,
    ) -> list[UUID]:
        """
        Process a trigger through matching agents.

        Args:
            trigger: The trigger event data
            tenant_config: Tenant configuration
            user_id: Optional user ID who triggered the event
            dry_run: If True, plan actions but don't execute

        Returns:
            List of execution IDs created
        """
        execution_ids = []

        # Find matching agents
        matching_agents = AgentRegistry.find_agents_for_trigger(trigger, tenant_config)

        if not matching_agents:
            self._logger.info(
                "No agents matched trigger",
                trigger_type=trigger.trigger_type.value,
                tenant_id=trigger.payload.get("tenant_id"),
            )
            return execution_ids

        # Process each matching agent
        for agent_class, agent_config in matching_agents:
            try:
                execution_id = await self._process_agent(
                    agent_class=agent_class,
                    agent_config=agent_config,
                    trigger=trigger,
                    tenant_config=tenant_config,
                    user_id=user_id,
                    dry_run=dry_run,
                )
                if execution_id:
                    execution_ids.append(execution_id)
            except Exception as e:
                self._logger.error(
                    "Agent processing failed",
                    agent_name=agent_class.__name__,
                    error=str(e),
                    exc_info=True,
                )
                # Continue with other agents

        return execution_ids

    async def _process_agent(
        self,
        agent_class: type[Agent],
        agent_config: dict,
        trigger: TriggerData,
        tenant_config: dict,
        user_id: str | None,
        dry_run: bool,
    ) -> UUID | None:
        """Process a single agent for a trigger."""
        agent = agent_class(agent_config)
        agent_name = agent.name

        # Create execution context
        context = ActionContext(
            agent_id=UUID(int=0),  # Will be set if using stored agents
            agent_name=agent_name,
            tenant_id=tenant_config.get("tenant_id", "default"),
            user_id=user_id,
            trigger_data=trigger,
            organization_settings=tenant_config,
            agent_config=agent_config,
            dry_run=dry_run,
        )

        # Check if agent should trigger
        should_trigger = await agent.should_trigger(trigger, context)
        if not should_trigger:
            self._logger.debug(
                "Agent declined trigger",
                agent_name=agent_name,
            )
            return None

        # Create execution record
        execution = ExecutionResult(
            execution_id=context.execution_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            status=ActionStatus.PENDING,
            trigger_data=trigger,
            started_at=datetime.now(timezone.utc),
            dry_run=dry_run,
        )

        await self.execution_repository.save(execution)

        try:
            # Plan actions
            start_time = datetime.now(timezone.utc)
            actions = await agent.plan_actions(trigger, context)

            if not actions:
                execution.status = ActionStatus.COMPLETED
                execution.completed_at = datetime.now(timezone.utc)
                await self.execution_repository.update(execution)
                return execution.execution_id

            # Process each action
            execution.status = ActionStatus.EXECUTING
            await self.execution_repository.update(execution)

            for action in actions:
                result = await self._process_action(agent, action, context)
                execution.action_results.append(result)

                # Update variables from result
                if result.result_data:
                    context.variables[f"action_{action.id}"] = result.result_data

                # Stop on failure unless configured otherwise
                if result.is_failure:
                    error_handling = agent_config.get("error_handling", {})
                    if error_handling.get("on_failure") == "stop":
                        break

            # Calculate final status
            if all(r.is_success or r.status == ActionStatus.SKIPPED for r in execution.action_results):
                execution.status = ActionStatus.COMPLETED
            elif any(r.status == ActionStatus.AWAITING_APPROVAL for r in execution.action_results):
                execution.status = ActionStatus.AWAITING_APPROVAL
            else:
                execution.status = ActionStatus.FAILED

            execution.completed_at = datetime.now(timezone.utc)
            duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.total_duration_ms = int(duration * 1000)
            execution.variables = context.variables

            # Record metrics
            AGENT_EXECUTIONS_TOTAL.labels(
                tenant_id=context.tenant_id,
                agent_name=agent_name,
                status=execution.status.value,
            ).inc()

            AGENT_EXECUTION_DURATION.labels(
                tenant_id=context.tenant_id,
                agent_name=agent_name,
            ).observe(duration)

            await self.execution_repository.update(execution)

            self._logger.info(
                "Agent execution completed",
                agent_name=agent_name,
                execution_id=str(execution.execution_id),
                status=execution.status.value,
                action_count=len(execution.action_results),
                duration_ms=execution.total_duration_ms,
            )

            return execution.execution_id

        except Exception as e:
            execution.status = ActionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            await self.execution_repository.update(execution)

            AGENT_EXECUTIONS_TOTAL.labels(
                tenant_id=context.tenant_id,
                agent_name=agent_name,
                status="failed",
            ).inc()

            raise

    async def _process_action(
        self,
        agent: Agent,
        action: Action,
        context: ActionContext,
    ) -> ActionResult:
        """Process a single action through approval and execution."""
        # Determine approval level
        approval_level = agent.get_approval_level(action, context)
        action.requires_approval = approval_level

        # Save action to repository
        await self.action_repository.save(action, agent.name, context)

        # Handle based on approval level
        if context.dry_run:
            # Dry run - just return what would happen
            return ActionResult(
                action_id=action.id,
                status=ActionStatus.SKIPPED,
                result_data={"dry_run": True, "would_execute": action.type.value},
            )

        if approval_level == ApprovalLevel.AUTO:
            # Execute immediately
            return await self._execute_action(agent, action, context)

        elif approval_level == ApprovalLevel.NOTIFY:
            # Execute and notify
            result = await self._execute_action(agent, action, context)
            await self._send_notification(action, result, context)
            return result

        elif approval_level == ApprovalLevel.REVIEW:
            # Request approval
            await self.approval_service.request_approval(
                action=action,
                context=context,
                agent_name=agent.name,
            )
            return ActionResult(
                action_id=action.id,
                status=ActionStatus.AWAITING_APPROVAL,
            )

        else:  # MANUAL
            # Just record, don't execute
            return ActionResult(
                action_id=action.id,
                status=ActionStatus.PENDING,
                result_data={"requires_manual_trigger": True},
            )

    async def _execute_action(
        self,
        agent: Agent,
        action: Action,
        context: ActionContext,
    ) -> ActionResult:
        """Execute an action with retry logic."""
        await self.action_repository.update_status(action.id, ActionStatus.EXECUTING)

        start_time = datetime.now(timezone.utc)

        try:
            # Pre-execution hook
            await agent.pre_execute(action, context)

            # Validate
            is_valid = await agent.validate_action(action, context)
            if not is_valid:
                raise ExecutionError("Action validation failed")

            # Execute with retry
            result = await self._execute_with_retry(agent, action, context)

            # Calculate execution time
            result.started_at = start_time
            result.mark_completed(result.result_data)

            # Update repository
            await self.action_repository.update_result(action.id, result)

            # Post-execution hooks
            await agent.post_execute(action, result, context)
            await agent.on_success(action, result, context)

            # Metrics
            ACTION_EXECUTIONS_TOTAL.labels(
                tenant_id=context.tenant_id,
                action_type=action.type.value,
                status="completed",
            ).inc()

            return result

        except Exception as e:
            result = ActionResult(
                action_id=action.id,
                status=ActionStatus.FAILED,
                started_at=start_time,
            )
            result.mark_failed(str(e))

            await self.action_repository.update_result(action.id, result)
            await agent.on_failure(action, result, context)

            ACTION_EXECUTIONS_TOTAL.labels(
                tenant_id=context.tenant_id,
                action_type=action.type.value,
                status="failed",
            ).inc()

            return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RetryableError),
    )
    async def _execute_with_retry(
        self,
        agent: Agent,
        action: Action,
        context: ActionContext,
    ) -> ActionResult:
        """Execute action with automatic retry on retryable errors."""
        try:
            return await asyncio.wait_for(
                agent.execute(action, context),
                timeout=action.timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise ExecutionError(f"Action timed out after {action.timeout_seconds}s")

    async def execute_approved_action(self, action_id: UUID) -> ActionResult:
        """Execute an action that has been approved."""
        action_record = await self.action_repository.get(action_id)
        if not action_record:
            raise ValueError(f"Action {action_id} not found")

        if action_record["status"] != ActionStatus.APPROVED.value:
            raise ValueError(f"Action {action_id} is not approved")

        agent_class = AgentRegistry.get_agent_class(action_record["agent_name"])
        if not agent_class:
            raise ValueError(f"Agent {action_record['agent_name']} not found")

        agent = agent_class(action_record.get("agent_config", {}))
        action = Action(**action_record["action"])
        context = ActionContext(**action_record["context"])

        return await self._execute_action(agent, action, context)

    async def cancel_execution(self, execution_id: UUID) -> bool:
        """Cancel a pending or running execution."""
        execution = await self.execution_repository.get(execution_id)
        if not execution:
            return False

        if execution.status not in [ActionStatus.PENDING, ActionStatus.EXECUTING]:
            return False

        execution.status = ActionStatus.CANCELLED
        execution.completed_at = datetime.now(timezone.utc)
        await self.execution_repository.update(execution)

        return True

    async def _send_notification(
        self,
        action: Action,
        result: ActionResult,
        context: ActionContext,
    ) -> None:
        """Send notification about executed action."""
        if not self.notification_client:
            return

        try:
            await self.notification_client.send(
                tenant_id=context.tenant_id,
                channel="slack",
                message={
                    "type": "action_executed",
                    "action_type": action.type.value,
                    "target": action.target_system,
                    "status": result.status.value,
                    "agent_name": context.agent_name,
                },
            )
        except Exception as e:
            self._logger.warning(
                "Failed to send notification",
                error=str(e),
            )
