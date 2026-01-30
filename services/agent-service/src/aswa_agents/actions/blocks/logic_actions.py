"""Logic control action blocks."""

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
    CompositeAction,
)

logger = structlog.get_logger()


class FilterAction(ActionBlock):
    """Filter data based on conditions."""

    action_type: ClassVar[str] = "filter"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC
    display_name: ClassVar[str] = "Filter"
    description: ClassVar[str] = "Filter data or control flow based on conditions"
    icon: ClassVar[str] = "filter"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["expression"],
        properties={
            "expression": {
                "type": "string",
                "description": "Boolean expression to evaluate",
            },
            "on_match": {
                "type": "string",
                "enum": ["continue", "skip"],
                "default": "continue",
                "description": "Action when expression matches",
            },
            "input_key": {
                "type": "string",
                "description": "Key to filter on (for array filtering)",
            },
            "output_key": {
                "type": "string",
                "default": "filtered",
                "description": "Key to store filtered results",
            },
        },
    )

    # Safe builtins for expression evaluation
    SAFE_BUILTINS = {
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "all": all,
        "any": any,
        "True": True,
        "False": False,
        "None": None,
    }

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute filter."""
        start_time = time.time()

        try:
            expression = self.config.get("expression")
            on_match = self.config.get("on_match", "continue")
            input_key = self.config.get("input_key")
            output_key = self.config.get("output_key", "filtered")

            if input_key:
                # Array filtering mode
                result = await self._filter_array(context, expression, input_key, output_key)
            else:
                # Flow control mode
                result = await self._evaluate_condition(context, expression, on_match, output_key)

            duration_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            self._logger.exception("Filter failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _filter_array(
        self,
        context: ActionContext,
        expression: str,
        input_key: str,
        output_key: str,
    ) -> ActionResult:
        """Filter array items based on expression."""
        # Get input array
        data = None
        for output in context.previous_outputs.values():
            if isinstance(output, dict) and input_key in output:
                data = output[input_key]
                break
        if data is None:
            data = context.variables.get(input_key) or context.trigger_data.get(input_key)

        if not isinstance(data, list):
            return self._create_result(
                status=ActionStatus.FAILED,
                error=f"Input '{input_key}' is not an array",
            )

        # Filter items
        filtered = []
        for item in data:
            eval_context = {
                "item": item,
                "trigger": context.trigger_data,
                "vars": context.variables,
            }
            if isinstance(item, dict):
                eval_context.update(item)

            if self._safe_eval(expression, eval_context):
                filtered.append(item)

        self._logger.info(
            "Array filtered",
            input_count=len(data),
            output_count=len(filtered),
        )

        return self._create_result(
            status=ActionStatus.SUCCESS,
            output={output_key: filtered, "count": len(filtered)},
        )

    async def _evaluate_condition(
        self,
        context: ActionContext,
        expression: str,
        on_match: str,
        output_key: str,
    ) -> ActionResult:
        """Evaluate condition for flow control."""
        # Build evaluation context
        eval_context = {
            "trigger": context.trigger_data,
            "vars": context.variables,
        }

        # Add previous outputs
        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                eval_context.update(output)
            safe_name = action_id.replace("-", "_").replace(" ", "_")
            eval_context[safe_name] = output

        # Add common helpers
        eval_context["confidence"] = context.trigger_data.get("confidence", 0)
        eval_context["sender"] = context.trigger_data.get("sender", "")
        eval_context["subject"] = context.trigger_data.get("subject", "")

        # Evaluate
        matches = self._safe_eval(expression, eval_context)

        if matches and on_match == "skip":
            return self._create_result(
                status=ActionStatus.SKIPPED,
                output={output_key: True, "matched": True, "action": "skip"},
            )
        elif not matches and on_match == "continue":
            return self._create_result(
                status=ActionStatus.SKIPPED,
                output={output_key: False, "matched": False, "action": "skip"},
            )

        return self._create_result(
            status=ActionStatus.SUCCESS,
            output={output_key: matches, "matched": matches, "action": "continue"},
        )

    def _safe_eval(self, expression: str, context: dict[str, Any]) -> bool:
        """Safely evaluate boolean expression."""
        safe_globals = {"__builtins__": self.SAFE_BUILTINS}
        safe_globals.update(context)

        try:
            code = compile(expression, "<expression>", "eval")
            result = eval(code, safe_globals, {})
            return bool(result)
        except Exception:
            return False


class BranchAction(CompositeAction):
    """Branch execution based on conditions."""

    action_type: ClassVar[str] = "branch"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC
    display_name: ClassVar[str] = "Branch"
    description: ClassVar[str] = "Branch execution into different paths"
    icon: ClassVar[str] = "git-branch"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["conditions"],
        properties={
            "conditions": {
                "type": "array",
                "description": "Array of {expression, actions} pairs",
            },
            "default_actions": {
                "type": "array",
                "description": "Actions to execute if no condition matches",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute branching logic."""
        start_time = time.time()

        try:
            conditions = self.config.get("conditions", [])
            default_actions = self.config.get("default_actions", [])

            # Evaluate each condition
            matched_branch = None
            for i, condition in enumerate(conditions):
                expression = condition.get("expression", "True")
                if self._evaluate_expression(expression, context):
                    matched_branch = i
                    break

            if matched_branch is not None:
                # Execute matched branch actions
                branch_actions = conditions[matched_branch].get("actions", [])
                self._logger.info(
                    "Branch matched",
                    branch_index=matched_branch,
                    action_count=len(branch_actions),
                )
                return self._create_result(
                    status=ActionStatus.SUCCESS,
                    output={
                        "matched_branch": matched_branch,
                        "branch_taken": "conditional",
                    },
                    duration_ms=(time.time() - start_time) * 1000,
                )
            else:
                # Execute default actions
                self._logger.info(
                    "Branch default",
                    action_count=len(default_actions),
                )
                return self._create_result(
                    status=ActionStatus.SUCCESS,
                    output={
                        "matched_branch": None,
                        "branch_taken": "default",
                    },
                    duration_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            self._logger.exception("Branch failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _evaluate_expression(self, expression: str, context: ActionContext) -> bool:
        """Evaluate boolean expression."""
        eval_context = {
            "trigger": context.trigger_data,
            "vars": context.variables,
            "True": True,
            "False": False,
            "None": None,
        }

        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                eval_context.update(output)

        try:
            return bool(eval(expression, {"__builtins__": {}}, eval_context))
        except Exception:
            return False


class LoopAction(CompositeAction):
    """Loop over items and execute actions for each."""

    action_type: ClassVar[str] = "loop"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC
    display_name: ClassVar[str] = "Loop"
    description: ClassVar[str] = "Loop over items and execute actions"
    icon: ClassVar[str] = "repeat"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["items_key"],
        properties={
            "items_key": {
                "type": "string",
                "description": "Key to get items from context",
            },
            "item_variable": {
                "type": "string",
                "default": "item",
                "description": "Variable name for current item",
            },
            "index_variable": {
                "type": "string",
                "default": "index",
                "description": "Variable name for current index",
            },
            "max_iterations": {
                "type": "integer",
                "default": 100,
                "description": "Maximum number of iterations",
            },
            "parallel": {
                "type": "boolean",
                "default": False,
                "description": "Execute iterations in parallel",
            },
            "output_key": {
                "type": "string",
                "default": "loop_results",
                "description": "Key to store loop results",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute loop."""
        start_time = time.time()

        try:
            items_key = self.config.get("items_key")
            item_variable = self.config.get("item_variable", "item")
            index_variable = self.config.get("index_variable", "index")
            max_iterations = self.config.get("max_iterations", 100)
            parallel = self.config.get("parallel", False)
            output_key = self.config.get("output_key", "loop_results")

            # Get items to iterate
            items = None
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and items_key in output:
                    items = output[items_key]
                    break
            if items is None:
                items = context.variables.get(items_key) or context.trigger_data.get(items_key)

            if not isinstance(items, list):
                return self._create_result(
                    status=ActionStatus.FAILED,
                    error=f"Items '{items_key}' is not an array",
                )

            # Limit iterations
            items = items[:max_iterations]

            # Track results
            results = []
            success_count = 0
            fail_count = 0

            if parallel:
                # Execute all iterations in parallel
                import asyncio

                async def execute_iteration(index: int, item: Any) -> dict:
                    iter_context = ActionContext(
                        agent_id=context.agent_id,
                        run_id=context.run_id,
                        tenant_id=context.tenant_id,
                        trigger_data=context.trigger_data,
                        variables={
                            **context.variables,
                            item_variable: item,
                            index_variable: index,
                        },
                        previous_outputs=context.previous_outputs,
                        secrets=context.secrets,
                    )
                    # Return iteration info (child actions would be executed by engine)
                    return {
                        "index": index,
                        "item": item,
                        "context": iter_context.model_dump(),
                    }

                tasks = [execute_iteration(i, item) for i, item in enumerate(items)]
                results = await asyncio.gather(*tasks)
            else:
                # Execute sequentially
                for i, item in enumerate(items):
                    results.append({
                        "index": i,
                        "item": item,
                    })

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Loop complete",
                item_count=len(items),
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={
                    output_key: results,
                    "item_count": len(items),
                    "success_count": len(results),
                },
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Loop failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )


class DelayAction(ActionBlock):
    """Delay execution for specified time."""

    action_type: ClassVar[str] = "delay"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC
    display_name: ClassVar[str] = "Delay"
    description: ClassVar[str] = "Pause execution for a specified time"
    icon: ClassVar[str] = "clock"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["duration"],
        properties={
            "duration": {
                "type": "integer",
                "description": "Delay duration in seconds",
            },
            "until": {
                "type": "string",
                "description": "Delay until specific time (ISO format)",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute delay."""
        import asyncio
        from datetime import datetime, timezone

        start_time = time.time()

        try:
            duration = self.config.get("duration", 0)
            until = self.config.get("until")

            if until:
                # Calculate delay until specified time
                target_time = datetime.fromisoformat(until.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                duration = max(0, (target_time - now).total_seconds())

            if duration > 0:
                self._logger.info("Delaying execution", duration_seconds=duration)
                await asyncio.sleep(duration)

            duration_ms = (time.time() - start_time) * 1000
            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={"delayed_seconds": duration},
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Delay failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )


class RetryAction(CompositeAction):
    """Retry child actions on failure."""

    action_type: ClassVar[str] = "retry"
    category: ClassVar[ActionCategory] = ActionCategory.LOGIC
    display_name: ClassVar[str] = "Retry"
    description: ClassVar[str] = "Retry actions on failure with backoff"
    icon: ClassVar[str] = "refresh-cw"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=[],
        properties={
            "max_attempts": {
                "type": "integer",
                "default": 3,
                "description": "Maximum retry attempts",
            },
            "backoff_seconds": {
                "type": "number",
                "default": 1.0,
                "description": "Initial backoff delay in seconds",
            },
            "backoff_multiplier": {
                "type": "number",
                "default": 2.0,
                "description": "Backoff multiplier for each retry",
            },
            "max_backoff": {
                "type": "number",
                "default": 60.0,
                "description": "Maximum backoff delay",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute with retry logic."""
        start_time = time.time()

        max_attempts = self.config.get("max_attempts", 3)
        backoff = self.config.get("backoff_seconds", 1.0)
        multiplier = self.config.get("backoff_multiplier", 2.0)
        max_backoff = self.config.get("max_backoff", 60.0)

        # This would be used by the execution engine to wrap child actions
        # For now, return configuration
        return self._create_result(
            status=ActionStatus.SUCCESS,
            output={
                "retry_config": {
                    "max_attempts": max_attempts,
                    "backoff_seconds": backoff,
                    "backoff_multiplier": multiplier,
                    "max_backoff": max_backoff,
                }
            },
            duration_ms=(time.time() - start_time) * 1000,
        )
