# Task 9.4.3: Logic Action Blocks

## Objective

Implement logic and control flow action blocks including conditions, branching, loops, and error handling for complex agent workflows.

## Prerequisites

- Task 9.4.1-9.4.2 completed (Core and Integration Action Blocks)

## Implementation

### Step 1: Condition Action Block

```python
# services/agent-service/src/aswa_agents/actions/logic/condition.py
"""Condition and branching action blocks."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class ConditionOperator(str, Enum):
    """Condition operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    MATCHES_REGEX = "matches_regex"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"


class ConditionRule(BaseModel):
    """A single condition rule."""

    field: str  # Path to field (e.g., "trigger.subject", "outputs.summarize.summary")
    operator: ConditionOperator
    value: Any = None  # Expected value for comparison
    case_sensitive: bool = False


class ConditionConfig(BaseModel):
    """Configuration for condition action."""

    rules: list[ConditionRule] = Field(..., min_length=1)
    logic: str = "AND"  # AND or OR
    true_branch: str | None = None  # Action ID to execute if true
    false_branch: str | None = None  # Action ID to execute if false
    stop_on_false: bool = False  # Stop execution if false


class ConditionOutput(BaseModel):
    """Output from condition action."""

    result: bool
    evaluated_rules: list[dict[str, Any]]
    next_action: str | None


class ConditionAction(ActionBlock[ConditionConfig, ConditionOutput]):
    """
    Evaluate conditions for branching logic.

    Supports multiple condition rules with AND/OR logic.
    Can route to different actions based on result.
    """

    action_type = "condition"
    display_name = "Condition"
    description = "Evaluate conditions and branch workflow"
    category = "logic"

    def __init__(self, action_id: str, config: ConditionConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute condition evaluation."""
        evaluated_rules = []
        results = []

        for rule in self.config.rules:
            field_value = self._get_field_value(rule.field, context)
            rule_result = self._evaluate_rule(rule, field_value)

            evaluated_rules.append({
                "field": rule.field,
                "operator": rule.operator.value,
                "expected": rule.value,
                "actual": field_value,
                "result": rule_result,
            })
            results.append(rule_result)

        # Apply logic
        if self.config.logic.upper() == "AND":
            final_result = all(results)
        else:  # OR
            final_result = any(results)

        # Determine next action
        if final_result:
            next_action = self.config.true_branch
        else:
            next_action = self.config.false_branch

        output = ConditionOutput(
            result=final_result,
            evaluated_rules=evaluated_rules,
            next_action=next_action,
        )

        # Handle stop on false
        if not final_result and self.config.stop_on_false:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.SKIPPED,
                output=output.model_dump(),
                metadata={"reason": "Condition evaluated to false, stopping execution"},
            )

        return ActionResult(
            action_id=self.action_id,
            status=ActionStatus.COMPLETED,
            output=output.model_dump(),
        )

    def _get_field_value(self, field_path: str, context: ActionContext) -> Any:
        """Get value from context using dot notation path."""
        parts = field_path.split(".")

        if parts[0] == "trigger":
            current = context.trigger_data
            parts = parts[1:]
        elif parts[0] == "outputs":
            if len(parts) < 2:
                return None
            action_id = parts[1]
            current = context.previous_outputs.get(action_id, {})
            parts = parts[2:]
        elif parts[0] == "vars":
            current = context.variables
            parts = parts[1:]
        else:
            # Try trigger data directly
            current = context.trigger_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                if idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None

        return current

    def _evaluate_rule(self, rule: ConditionRule, actual_value: Any) -> bool:
        """Evaluate a single condition rule."""
        import re

        # Normalize values for comparison
        actual = actual_value
        expected = rule.value

        if not rule.case_sensitive and isinstance(actual, str):
            actual = actual.lower()
        if not rule.case_sensitive and isinstance(expected, str):
            expected = expected.lower()

        match rule.operator:
            case ConditionOperator.EQUALS:
                return actual == expected

            case ConditionOperator.NOT_EQUALS:
                return actual != expected

            case ConditionOperator.CONTAINS:
                if isinstance(actual, str):
                    return str(expected) in actual
                elif isinstance(actual, (list, dict)):
                    return expected in actual
                return False

            case ConditionOperator.NOT_CONTAINS:
                if isinstance(actual, str):
                    return str(expected) not in actual
                elif isinstance(actual, (list, dict)):
                    return expected not in actual
                return True

            case ConditionOperator.STARTS_WITH:
                return isinstance(actual, str) and actual.startswith(str(expected))

            case ConditionOperator.ENDS_WITH:
                return isinstance(actual, str) and actual.endswith(str(expected))

            case ConditionOperator.GREATER_THAN:
                try:
                    return float(actual) > float(expected)
                except (TypeError, ValueError):
                    return False

            case ConditionOperator.LESS_THAN:
                try:
                    return float(actual) < float(expected)
                except (TypeError, ValueError):
                    return False

            case ConditionOperator.GREATER_OR_EQUAL:
                try:
                    return float(actual) >= float(expected)
                except (TypeError, ValueError):
                    return False

            case ConditionOperator.LESS_OR_EQUAL:
                try:
                    return float(actual) <= float(expected)
                except (TypeError, ValueError):
                    return False

            case ConditionOperator.IS_EMPTY:
                return actual is None or actual == "" or actual == [] or actual == {}

            case ConditionOperator.IS_NOT_EMPTY:
                return actual is not None and actual != "" and actual != [] and actual != {}

            case ConditionOperator.MATCHES_REGEX:
                if isinstance(actual, str) and isinstance(expected, str):
                    try:
                        return bool(re.match(expected, actual))
                    except re.error:
                        return False
                return False

            case ConditionOperator.IN_LIST:
                if isinstance(expected, list):
                    return actual in expected
                return False

            case ConditionOperator.NOT_IN_LIST:
                if isinstance(expected, list):
                    return actual not in expected
                return True

        return False

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return ConditionConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return ConditionOutput.model_json_schema()
```

### Step 2: Loop Action Block

```python
# services/agent-service/src/aswa_agents/actions/logic/loop.py
"""Loop and iteration action blocks."""

from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class LoopConfig(BaseModel):
    """Configuration for loop action."""

    items_field: str  # Field containing items to iterate
    item_variable: str = "item"  # Variable name for current item
    index_variable: str = "index"  # Variable name for current index
    max_iterations: int = Field(default=100, ge=1, le=1000)
    actions: list[str] = Field(default_factory=list)  # Action IDs to execute per item
    break_on_error: bool = True
    parallel: bool = False  # Execute items in parallel


class LoopOutput(BaseModel):
    """Output from loop action."""

    total_items: int
    processed_items: int
    failed_items: int
    results: list[dict[str, Any]]
    break_reason: str | None = None


class LoopAction(ActionBlock[LoopConfig, LoopOutput]):
    """
    Iterate over a collection and execute actions.

    Supports sequential and parallel execution.
    Tracks progress and handles errors.
    """

    action_type = "loop"
    display_name = "Loop"
    description = "Iterate over items and execute actions"
    category = "logic"

    def __init__(self, action_id: str, config: LoopConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute loop."""
        # Get items to iterate
        items = self._get_items(context)

        if items is None:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"No items found at field '{self.config.items_field}'",
            )

        if not isinstance(items, (list, tuple)):
            items = [items]

        # Limit iterations
        items = items[:self.config.max_iterations]

        results = []
        processed = 0
        failed = 0
        break_reason = None

        if self.config.parallel:
            # Parallel execution
            import asyncio

            async def process_item(idx: int, item: Any) -> dict:
                return await self._process_item(context, idx, item)

            tasks = [process_item(i, item) for i, item in enumerate(items)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    failed += 1
                else:
                    processed += 1
                    if not r.get("success", True):
                        failed += 1

        else:
            # Sequential execution
            for idx, item in enumerate(items):
                try:
                    result = await self._process_item(context, idx, item)
                    results.append(result)
                    processed += 1

                    if not result.get("success", True):
                        failed += 1
                        if self.config.break_on_error:
                            break_reason = f"Error at index {idx}"
                            break

                except Exception as e:
                    failed += 1
                    results.append({
                        "index": idx,
                        "success": False,
                        "error": str(e),
                    })

                    if self.config.break_on_error:
                        break_reason = f"Exception at index {idx}: {str(e)}"
                        break

        output = LoopOutput(
            total_items=len(items),
            processed_items=processed,
            failed_items=failed,
            results=results,
            break_reason=break_reason,
        )

        status = ActionStatus.COMPLETED if failed == 0 else ActionStatus.COMPLETED
        if break_reason and self.config.break_on_error:
            status = ActionStatus.FAILED

        return ActionResult(
            action_id=self.action_id,
            status=status,
            output=output.model_dump(),
        )

    def _get_items(self, context: ActionContext) -> Any:
        """Get items from context."""
        parts = self.config.items_field.split(".")

        if parts[0] == "trigger":
            current = context.trigger_data
            parts = parts[1:]
        elif parts[0] == "outputs":
            if len(parts) < 2:
                return None
            current = context.previous_outputs.get(parts[1], {})
            parts = parts[2:]
        else:
            current = context.trigger_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    async def _process_item(
        self, context: ActionContext, index: int, item: Any
    ) -> dict[str, Any]:
        """Process a single item in the loop."""
        # Create item context with loop variables
        item_context = ActionContext(
            execution_id=context.execution_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            trigger_data=context.trigger_data,
            previous_outputs=context.previous_outputs.copy(),
            variables={
                **context.variables,
                self.config.item_variable: item,
                self.config.index_variable: index,
            },
            metadata=context.metadata,
        )

        # For now, just return success with item info
        # Full implementation would execute nested actions
        return {
            "index": index,
            "item": item,
            "success": True,
        }

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return LoopConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return LoopOutput.model_json_schema()
```

### Step 3: Switch Action Block

```python
# services/agent-service/src/aswa_agents/actions/logic/switch.py
"""Switch/case action block."""

from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class SwitchCase(BaseModel):
    """A single case in a switch statement."""

    value: Any  # Value to match
    actions: list[str] = Field(default_factory=list)  # Action IDs to execute
    label: str = ""  # Human-readable label


class SwitchConfig(BaseModel):
    """Configuration for switch action."""

    field: str  # Field to evaluate
    cases: list[SwitchCase] = Field(default_factory=list)
    default_actions: list[str] = Field(default_factory=list)
    case_sensitive: bool = False


class SwitchOutput(BaseModel):
    """Output from switch action."""

    evaluated_value: Any
    matched_case: str | None
    selected_actions: list[str]


class SwitchAction(ActionBlock[SwitchConfig, SwitchOutput]):
    """
    Switch/case control flow.

    Evaluates a field and routes to different actions
    based on the value.
    """

    action_type = "switch"
    display_name = "Switch"
    description = "Route to different actions based on value"
    category = "logic"

    def __init__(self, action_id: str, config: SwitchConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute switch evaluation."""
        # Get value to switch on
        value = self._get_field_value(context)

        # Normalize for comparison
        compare_value = value
        if not self.config.case_sensitive and isinstance(compare_value, str):
            compare_value = compare_value.lower()

        # Find matching case
        matched_case = None
        selected_actions = []

        for case in self.config.cases:
            case_value = case.value
            if not self.config.case_sensitive and isinstance(case_value, str):
                case_value = case_value.lower()

            if compare_value == case_value:
                matched_case = case.label or str(case.value)
                selected_actions = case.actions
                break

        # Use default if no match
        if matched_case is None:
            matched_case = "default"
            selected_actions = self.config.default_actions

        output = SwitchOutput(
            evaluated_value=value,
            matched_case=matched_case,
            selected_actions=selected_actions,
        )

        return ActionResult(
            action_id=self.action_id,
            status=ActionStatus.COMPLETED,
            output=output.model_dump(),
        )

    def _get_field_value(self, context: ActionContext) -> Any:
        """Get field value from context."""
        parts = self.config.field.split(".")

        if parts[0] == "trigger":
            current = context.trigger_data
            parts = parts[1:]
        elif parts[0] == "outputs":
            if len(parts) < 2:
                return None
            current = context.previous_outputs.get(parts[1], {})
            parts = parts[2:]
        else:
            current = context.trigger_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return SwitchConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return SwitchOutput.model_json_schema()
```

### Step 4: Wait Action Block

```python
# services/agent-service/src/aswa_agents/actions/logic/wait.py
"""Wait and delay action blocks."""

import asyncio
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class WaitType(str, Enum):
    """Type of wait."""

    DELAY = "delay"  # Fixed delay
    SCHEDULE = "schedule"  # Wait until specific time
    CONDITION = "condition"  # Wait for condition


class WaitConfig(BaseModel):
    """Configuration for wait action."""

    wait_type: WaitType = WaitType.DELAY
    delay_seconds: int = Field(default=5, ge=1, le=86400)  # Max 24 hours
    schedule_time: str | None = None  # ISO timestamp
    condition_field: str | None = None  # Field to check for condition
    condition_value: Any = None  # Expected value
    max_wait_seconds: int = Field(default=3600, ge=1, le=86400)
    poll_interval_seconds: int = Field(default=5, ge=1, le=60)


class WaitOutput(BaseModel):
    """Output from wait action."""

    waited_seconds: float
    reason: str


class WaitAction(ActionBlock[WaitConfig, WaitOutput]):
    """
    Wait or delay action.

    Supports fixed delays, scheduled waits, and condition-based waits.
    """

    action_type = "wait"
    display_name = "Wait"
    description = "Wait before continuing workflow"
    category = "logic"

    def __init__(self, action_id: str, config: WaitConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute wait."""
        import time

        start = time.monotonic()

        try:
            if self.config.wait_type == WaitType.DELAY:
                await self._wait_delay()
                reason = f"Delayed for {self.config.delay_seconds} seconds"

            elif self.config.wait_type == WaitType.SCHEDULE:
                await self._wait_schedule()
                reason = f"Waited until scheduled time"

            elif self.config.wait_type == WaitType.CONDITION:
                met = await self._wait_condition(context)
                reason = "Condition met" if met else "Condition timeout"

            else:
                reason = "Unknown wait type"

            waited = time.monotonic() - start

            output = WaitOutput(
                waited_seconds=waited,
                reason=reason,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except asyncio.CancelledError:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="Wait was cancelled",
            )

    async def _wait_delay(self) -> None:
        """Wait for fixed delay."""
        await asyncio.sleep(self.config.delay_seconds)

    async def _wait_schedule(self) -> None:
        """Wait until scheduled time."""
        from datetime import datetime

        if not self.config.schedule_time:
            return

        target = datetime.fromisoformat(self.config.schedule_time.replace("Z", "+00:00"))
        now = datetime.now(target.tzinfo)

        if target > now:
            wait_seconds = (target - now).total_seconds()
            wait_seconds = min(wait_seconds, self.config.max_wait_seconds)
            await asyncio.sleep(wait_seconds)

    async def _wait_condition(self, context: ActionContext) -> bool:
        """Wait for condition to be met."""
        import time

        if not self.config.condition_field:
            return True

        start = time.monotonic()

        while (time.monotonic() - start) < self.config.max_wait_seconds:
            # Check condition
            value = self._get_field_value(self.config.condition_field, context)

            if value == self.config.condition_value:
                return True

            await asyncio.sleep(self.config.poll_interval_seconds)

        return False

    def _get_field_value(self, field: str, context: ActionContext) -> Any:
        """Get field value from context."""
        parts = field.split(".")

        if parts[0] == "trigger":
            current = context.trigger_data
            parts = parts[1:]
        elif parts[0] == "outputs":
            current = context.previous_outputs.get(parts[1], {}) if len(parts) > 1 else {}
            parts = parts[2:]
        else:
            current = context.trigger_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return WaitConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return WaitOutput.model_json_schema()
```

### Step 5: Error Handler Action Block

```python
# services/agent-service/src/aswa_agents/actions/logic/error_handler.py
"""Error handling action block."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class ErrorHandling(str, Enum):
    """Error handling strategies."""

    RETRY = "retry"
    FALLBACK = "fallback"
    IGNORE = "ignore"
    FAIL = "fail"


class RetryConfig(BaseModel):
    """Retry configuration."""

    max_retries: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=1.0, ge=0.1, le=60)
    backoff_multiplier: float = Field(default=2.0, ge=1, le=10)
    max_delay_seconds: float = Field(default=60, ge=1, le=300)


class ErrorHandlerConfig(BaseModel):
    """Configuration for error handler action."""

    strategy: ErrorHandling = ErrorHandling.RETRY
    retry: RetryConfig = Field(default_factory=RetryConfig)
    fallback_actions: list[str] = Field(default_factory=list)
    notify_on_error: bool = False
    notification_channel: str | None = None
    capture_error_details: bool = True


class ErrorHandlerOutput(BaseModel):
    """Output from error handler action."""

    handled: bool
    strategy_used: str
    retry_count: int = 0
    error_details: dict[str, Any] | None = None
    fallback_executed: bool = False


class ErrorHandlerAction(ActionBlock[ErrorHandlerConfig, ErrorHandlerOutput]):
    """
    Handle errors in workflow execution.

    Provides retry, fallback, and notification capabilities.
    Wraps other actions with error handling logic.
    """

    action_type = "error_handler"
    display_name = "Error Handler"
    description = "Handle errors with retry and fallback"
    category = "logic"

    def __init__(self, action_id: str, config: ErrorHandlerConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute error handling logic."""
        # This action is typically used as a wrapper
        # It checks the last action's result and handles errors

        last_output = self._get_last_action_result(context)

        if last_output and last_output.get("status") == "failed":
            return await self._handle_error(context, last_output)

        output = ErrorHandlerOutput(
            handled=False,
            strategy_used="none",
        )

        return ActionResult(
            action_id=self.action_id,
            status=ActionStatus.COMPLETED,
            output=output.model_dump(),
        )

    async def _handle_error(
        self, context: ActionContext, error_info: dict
    ) -> ActionResult:
        """Handle an error based on configured strategy."""
        import asyncio

        strategy = self.config.strategy
        output = ErrorHandlerOutput(
            handled=True,
            strategy_used=strategy.value,
            error_details=error_info if self.config.capture_error_details else None,
        )

        if strategy == ErrorHandling.IGNORE:
            # Just continue
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        elif strategy == ErrorHandling.FAIL:
            # Propagate the error
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                output=output.model_dump(),
                error=error_info.get("error", "Previous action failed"),
            )

        elif strategy == ErrorHandling.FALLBACK:
            # Execute fallback actions
            output.fallback_executed = True
            # In real implementation, would trigger fallback actions
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
                metadata={"fallback_actions": self.config.fallback_actions},
            )

        elif strategy == ErrorHandling.RETRY:
            # Retry logic would be handled by orchestrator
            output.retry_count = self.config.retry.max_retries
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
                metadata={
                    "retry_requested": True,
                    "retry_config": self.config.retry.model_dump(),
                },
            )

        return ActionResult(
            action_id=self.action_id,
            status=ActionStatus.COMPLETED,
            output=output.model_dump(),
        )

    def _get_last_action_result(self, context: ActionContext) -> dict | None:
        """Get the last action's result from context."""
        if not context.previous_outputs:
            return None

        # Get the most recent output
        last_key = list(context.previous_outputs.keys())[-1]
        return context.previous_outputs.get(last_key)

    async def wrap_action(
        self,
        action: ActionBlock,
        context: ActionContext,
    ) -> ActionResult:
        """
        Wrap another action with error handling.

        This is called by the orchestrator to add error handling
        to an action's execution.
        """
        import asyncio

        retry_count = 0
        last_error = None
        delay = self.config.retry.initial_delay_seconds

        while retry_count <= self.config.retry.max_retries:
            try:
                result = await action.run(context)

                if result.is_success:
                    return result

                if self.config.strategy != ErrorHandling.RETRY:
                    # Handle according to strategy
                    return await self._handle_non_retry_error(result)

                last_error = result.error
                retry_count += 1

                if retry_count <= self.config.retry.max_retries:
                    self._logger.info(
                        "Retrying action",
                        action_id=action.action_id,
                        retry=retry_count,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self.config.retry.backoff_multiplier,
                        self.config.retry.max_delay_seconds,
                    )

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                if retry_count <= self.config.retry.max_retries:
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self.config.retry.backoff_multiplier,
                        self.config.retry.max_delay_seconds,
                    )

        # All retries exhausted
        if self.config.notify_on_error:
            await self._send_error_notification(action, last_error, context)

        return ActionResult(
            action_id=action.action_id,
            status=ActionStatus.FAILED,
            error=f"Failed after {retry_count} retries: {last_error}",
        )

    async def _handle_non_retry_error(self, result: ActionResult) -> ActionResult:
        """Handle error when not using retry strategy."""
        if self.config.strategy == ErrorHandling.IGNORE:
            result.status = ActionStatus.COMPLETED
            return result

        elif self.config.strategy == ErrorHandling.FALLBACK:
            # Would execute fallback actions
            pass

        return result

    async def _send_error_notification(
        self,
        action: ActionBlock,
        error: str,
        context: ActionContext,
    ) -> None:
        """Send error notification."""
        if not self.config.notification_channel:
            return

        # In real implementation, would send notification
        self._logger.info(
            "Error notification sent",
            action_id=action.action_id,
            channel=self.config.notification_channel,
            error=error,
        )

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return ErrorHandlerConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return ErrorHandlerOutput.model_json_schema()
```

## Test Cases

```python
# services/agent-service/tests/unit/test_logic_actions.py
"""Tests for logic action blocks."""

import pytest
from uuid import uuid4

from aswa_agents.actions.base import ActionContext, ActionStatus
from aswa_agents.actions.logic.condition import (
    ConditionAction,
    ConditionConfig,
    ConditionOperator,
    ConditionRule,
)
from aswa_agents.actions.logic.loop import LoopAction, LoopConfig
from aswa_agents.actions.logic.switch import SwitchAction, SwitchConfig, SwitchCase
from aswa_agents.actions.logic.wait import WaitAction, WaitConfig, WaitType
from aswa_agents.actions.logic.error_handler import (
    ErrorHandlerAction,
    ErrorHandlerConfig,
    ErrorHandling,
)


@pytest.fixture
def context():
    """Create test context."""
    return ActionContext(
        execution_id=uuid4(),
        agent_id=uuid4(),
        tenant_id="test-tenant",
        trigger_data={
            "status": "urgent",
            "priority": 5,
            "message": "Hello World",
            "items": ["a", "b", "c"],
        },
        previous_outputs={
            "extract": {
                "count": 10,
                "items": [{"id": 1}, {"id": 2}],
            }
        },
    )


class TestConditionAction:
    """Test ConditionAction."""

    @pytest.mark.asyncio
    async def test_equals_condition_true(self, context):
        """Test equals condition that evaluates to true."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.status",
                    operator=ConditionOperator.EQUALS,
                    value="urgent",
                )
            ],
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_equals_condition_false(self, context):
        """Test equals condition that evaluates to false."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.status",
                    operator=ConditionOperator.EQUALS,
                    value="normal",
                )
            ],
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["result"] is False

    @pytest.mark.asyncio
    async def test_contains_condition(self, context):
        """Test contains condition."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.message",
                    operator=ConditionOperator.CONTAINS,
                    value="World",
                )
            ],
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_greater_than_condition(self, context):
        """Test greater than condition."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.priority",
                    operator=ConditionOperator.GREATER_THAN,
                    value=3,
                )
            ],
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_and_logic(self, context):
        """Test AND logic with multiple rules."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.status",
                    operator=ConditionOperator.EQUALS,
                    value="urgent",
                ),
                ConditionRule(
                    field="trigger.priority",
                    operator=ConditionOperator.GREATER_THAN,
                    value=10,  # False
                ),
            ],
            logic="AND",
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.output["result"] is False

    @pytest.mark.asyncio
    async def test_or_logic(self, context):
        """Test OR logic with multiple rules."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.status",
                    operator=ConditionOperator.EQUALS,
                    value="urgent",  # True
                ),
                ConditionRule(
                    field="trigger.priority",
                    operator=ConditionOperator.GREATER_THAN,
                    value=10,  # False
                ),
            ],
            logic="OR",
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.output["result"] is True

    @pytest.mark.asyncio
    async def test_stop_on_false(self, context):
        """Test stop on false configuration."""
        config = ConditionConfig(
            rules=[
                ConditionRule(
                    field="trigger.status",
                    operator=ConditionOperator.EQUALS,
                    value="normal",
                )
            ],
            stop_on_false=True,
        )
        action = ConditionAction("test-condition", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.SKIPPED


class TestLoopAction:
    """Test LoopAction."""

    @pytest.mark.asyncio
    async def test_loop_over_list(self, context):
        """Test looping over a list."""
        config = LoopConfig(
            items_field="trigger.items",
        )
        action = LoopAction("test-loop", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["total_items"] == 3
        assert result.output["processed_items"] == 3

    @pytest.mark.asyncio
    async def test_loop_from_output(self, context):
        """Test looping over previous action output."""
        config = LoopConfig(
            items_field="outputs.extract.items",
        )
        action = LoopAction("test-loop", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["total_items"] == 2


class TestSwitchAction:
    """Test SwitchAction."""

    @pytest.mark.asyncio
    async def test_switch_match(self, context):
        """Test switch with matching case."""
        config = SwitchConfig(
            field="trigger.status",
            cases=[
                SwitchCase(value="urgent", actions=["notify_urgent"], label="Urgent"),
                SwitchCase(value="normal", actions=["notify_normal"], label="Normal"),
            ],
            default_actions=["notify_default"],
        )
        action = SwitchAction("test-switch", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["matched_case"] == "Urgent"
        assert result.output["selected_actions"] == ["notify_urgent"]

    @pytest.mark.asyncio
    async def test_switch_default(self, context):
        """Test switch falling through to default."""
        context.trigger_data["status"] = "unknown"
        config = SwitchConfig(
            field="trigger.status",
            cases=[
                SwitchCase(value="urgent", actions=["notify_urgent"]),
            ],
            default_actions=["notify_default"],
        )
        action = SwitchAction("test-switch", config)

        result = await action.execute(context)

        assert result.output["matched_case"] == "default"
        assert result.output["selected_actions"] == ["notify_default"]


class TestWaitAction:
    """Test WaitAction."""

    @pytest.mark.asyncio
    async def test_delay_wait(self, context):
        """Test delay wait."""
        config = WaitConfig(
            wait_type=WaitType.DELAY,
            delay_seconds=1,
        )
        action = WaitAction("test-wait", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["waited_seconds"] >= 1


class TestErrorHandlerAction:
    """Test ErrorHandlerAction."""

    @pytest.mark.asyncio
    async def test_no_error(self, context):
        """Test when there's no error."""
        config = ErrorHandlerConfig(strategy=ErrorHandling.RETRY)
        action = ErrorHandlerAction("test-error", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["handled"] is False

    @pytest.mark.asyncio
    async def test_handle_error_with_ignore(self, context):
        """Test ignoring an error."""
        context.previous_outputs["failed_action"] = {
            "status": "failed",
            "error": "Test error",
        }
        config = ErrorHandlerConfig(strategy=ErrorHandling.IGNORE)
        action = ErrorHandlerAction("test-error", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["handled"] is True
        assert result.output["strategy_used"] == "ignore"

    @pytest.mark.asyncio
    async def test_handle_error_with_fail(self, context):
        """Test propagating an error."""
        context.previous_outputs["failed_action"] = {
            "status": "failed",
            "error": "Test error",
        }
        config = ErrorHandlerConfig(strategy=ErrorHandling.FAIL)
        action = ErrorHandlerAction("test-error", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_logic_actions.py -v
   ```

2. **Test condition evaluation:**
   ```python
   from aswa_agents.actions.logic.condition import *
   from aswa_agents.actions.base import ActionContext
   from uuid import uuid4

   config = ConditionConfig(
       rules=[
           ConditionRule(field="trigger.priority", operator=ConditionOperator.GREATER_THAN, value=5)
       ]
   )
   action = ConditionAction("test", config)

   context = ActionContext(
       execution_id=uuid4(),
       agent_id=uuid4(),
       tenant_id="test",
       trigger_data={"priority": 10}
   )

   result = await action.run(context)
   print(f"Condition result: {result.output['result']}")
   ```

3. **Test loop execution:**
   ```python
   from aswa_agents.actions.logic.loop import *

   config = LoopConfig(items_field="trigger.items")
   action = LoopAction("test", config)

   context = ActionContext(
       execution_id=uuid4(),
       agent_id=uuid4(),
       tenant_id="test",
       trigger_data={"items": ["a", "b", "c"]}
   )

   result = await action.run(context)
   print(f"Processed: {result.output['processed_items']}")
   ```

## Next Task

Proceed to `task-9.4.4-action-block-registry.md` for implementing the action block registry.
