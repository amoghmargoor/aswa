"""Data processing action blocks."""

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


class SummarizeAction(ActionBlock):
    """Summarize content using AI."""

    action_type: ClassVar[str] = "summarize"
    category: ClassVar[ActionCategory] = ActionCategory.DATA
    display_name: ClassVar[str] = "Summarize"
    description: ClassVar[str] = "Generate a summary of the input content"
    icon: ClassVar[str] = "file-text"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=[],
        properties={
            "style": {
                "type": "string",
                "enum": ["brief", "detailed", "bullet_points"],
                "default": "brief",
                "description": "Summary style",
            },
            "max_length": {
                "type": "integer",
                "default": 500,
                "description": "Maximum summary length in characters",
            },
            "input_key": {
                "type": "string",
                "default": "content",
                "description": "Key to get input content from context",
            },
            "output_key": {
                "type": "string",
                "default": "summary",
                "description": "Key to store summary in output",
            },
            "include_key_points": {
                "type": "boolean",
                "default": False,
                "description": "Include key points extraction",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute summarization."""
        start_time = time.time()

        try:
            style = self.config.get("style", "brief")
            max_length = self.config.get("max_length", 500)
            input_key = self.config.get("input_key", "content")
            output_key = self.config.get("output_key", "summary")
            include_key_points = self.config.get("include_key_points", False)

            # Get input content
            content = context.trigger_data.get(input_key) or context.get_variable(input_key)
            if not content:
                # Check previous outputs
                for prev_output in context.previous_outputs.values():
                    if isinstance(prev_output, dict) and input_key in prev_output:
                        content = prev_output[input_key]
                        break
                    elif isinstance(prev_output, str):
                        content = prev_output
                        break

            if not content:
                return self._create_result(
                    status=ActionStatus.FAILED,
                    error=f"No input content found for key: {input_key}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Generate summary using LLM
            summary = await self._generate_summary(content, style, max_length)

            output = {output_key: summary}

            if include_key_points:
                key_points = await self._extract_key_points(content)
                output["key_points"] = key_points

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Summarization complete",
                input_length=len(str(content)),
                output_length=len(summary),
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output=output,
                duration_ms=duration_ms,
                style=style,
            )

        except Exception as e:
            self._logger.exception("Summarization failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _generate_summary(self, content: str, style: str, max_length: int) -> str:
        """Generate summary using LLM."""
        # This would integrate with the LLM service
        # For now, return a placeholder
        from aswa_agents.generation.prompts import SUMMARIZATION_PROMPTS

        prompt = SUMMARIZATION_PROMPTS.get(style, SUMMARIZATION_PROMPTS["brief"])

        # TODO: Integrate with actual LLM service
        # For now, return truncated content as placeholder
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content

    async def _extract_key_points(self, content: str) -> list[str]:
        """Extract key points from content."""
        # TODO: Integrate with actual LLM service
        return ["Key point 1", "Key point 2", "Key point 3"]


class ExtractAction(ActionBlock):
    """Extract structured data from content."""

    action_type: ClassVar[str] = "extract"
    category: ClassVar[ActionCategory] = ActionCategory.DATA
    display_name: ClassVar[str] = "Extract"
    description: ClassVar[str] = "Extract structured data from content"
    icon: ClassVar[str] = "database"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["extraction_type"],
        properties={
            "extraction_type": {
                "type": "string",
                "enum": ["entities", "action_items", "dates", "numbers", "custom"],
                "description": "Type of extraction to perform",
            },
            "custom_schema": {
                "type": "object",
                "description": "Custom extraction schema (for extraction_type=custom)",
            },
            "input_key": {
                "type": "string",
                "default": "content",
                "description": "Key to get input content from context",
            },
            "output_key": {
                "type": "string",
                "default": "extracted",
                "description": "Key to store extracted data in output",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute extraction."""
        start_time = time.time()

        try:
            extraction_type = self.config.get("extraction_type", "entities")
            input_key = self.config.get("input_key", "content")
            output_key = self.config.get("output_key", "extracted")

            # Get input content
            content = context.trigger_data.get(input_key) or context.get_variable(input_key)
            if not content:
                for prev_output in context.previous_outputs.values():
                    if isinstance(prev_output, dict) and input_key in prev_output:
                        content = prev_output[input_key]
                        break

            if not content:
                return self._create_result(
                    status=ActionStatus.FAILED,
                    error=f"No input content found for key: {input_key}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Perform extraction based on type
            if extraction_type == "entities":
                extracted = await self._extract_entities(content)
            elif extraction_type == "action_items":
                extracted = await self._extract_action_items(content)
            elif extraction_type == "dates":
                extracted = await self._extract_dates(content)
            elif extraction_type == "numbers":
                extracted = await self._extract_numbers(content)
            elif extraction_type == "custom":
                custom_schema = self.config.get("custom_schema", {})
                extracted = await self._extract_custom(content, custom_schema)
            else:
                extracted = {}

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Extraction complete",
                extraction_type=extraction_type,
                item_count=len(extracted) if isinstance(extracted, list) else 1,
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={output_key: extracted},
                duration_ms=duration_ms,
                extraction_type=extraction_type,
            )

        except Exception as e:
            self._logger.exception("Extraction failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _extract_entities(self, content: str) -> list[dict[str, Any]]:
        """Extract named entities."""
        # TODO: Integrate with NLP/LLM service
        return [
            {"type": "PERSON", "text": "Sample Person", "confidence": 0.9},
            {"type": "ORG", "text": "Sample Org", "confidence": 0.85},
        ]

    async def _extract_action_items(self, content: str) -> list[dict[str, Any]]:
        """Extract action items."""
        return [
            {"text": "Sample action item", "assignee": None, "due_date": None},
        ]

    async def _extract_dates(self, content: str) -> list[dict[str, Any]]:
        """Extract dates from content."""
        import re
        from datetime import datetime

        # Simple date pattern matching
        patterns = [
            r"\d{4}-\d{2}-\d{2}",  # ISO format
            r"\d{1,2}/\d{1,2}/\d{4}",  # US format
        ]

        dates = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                dates.append({"raw": match, "normalized": match})

        return dates

    async def _extract_numbers(self, content: str) -> list[dict[str, Any]]:
        """Extract numbers from content."""
        import re

        numbers = []
        # Match numbers with optional currency symbols
        pattern = r"[\$€£]?\d+(?:,\d{3})*(?:\.\d+)?%?"
        matches = re.findall(pattern, content)

        for match in matches:
            is_currency = any(c in match for c in "$€£")
            is_percentage = match.endswith("%")
            numbers.append({
                "raw": match,
                "type": "currency" if is_currency else "percentage" if is_percentage else "number",
            })

        return numbers

    async def _extract_custom(self, content: str, schema: dict) -> dict[str, Any]:
        """Extract data according to custom schema."""
        # TODO: Use LLM to extract according to schema
        return {}


class TransformAction(ActionBlock):
    """Transform data using expressions or mappings."""

    action_type: ClassVar[str] = "transform"
    category: ClassVar[ActionCategory] = ActionCategory.DATA
    display_name: ClassVar[str] = "Transform"
    description: ClassVar[str] = "Transform data using expressions"
    icon: ClassVar[str] = "git-branch"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["expression"],
        properties={
            "expression": {
                "type": "string",
                "description": "Transform expression (Python-like syntax)",
            },
            "input_key": {
                "type": "string",
                "default": "input",
                "description": "Key to get input data from context",
            },
            "output_key": {
                "type": "string",
                "default": "transformed",
                "description": "Key to store transformed data",
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
        "list": list,
        "dict": dict,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "reversed": reversed,
        "zip": zip,
        "enumerate": enumerate,
        "range": range,
        "map": map,
        "filter": filter,
        "all": all,
        "any": any,
        "True": True,
        "False": False,
        "None": None,
    }

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute transformation."""
        start_time = time.time()

        try:
            expression = self.config.get("expression", "input")
            input_key = self.config.get("input_key", "input")
            output_key = self.config.get("output_key", "transformed")

            # Build evaluation context
            eval_context = {
                "input": context.trigger_data.get(input_key) or context.get_variable(input_key),
                "trigger": context.trigger_data,
                "vars": context.variables,
                "prev": context.previous_outputs,
            }

            # Add previous outputs as named variables
            for action_id, output in context.previous_outputs.items():
                safe_name = action_id.replace("-", "_").replace(" ", "_")
                eval_context[safe_name] = output

            # Evaluate expression safely
            result = self._safe_eval(expression, eval_context)

            duration_ms = (time.time() - start_time) * 1000
            self._logger.info(
                "Transform complete",
                expression=expression[:100],
                duration_ms=duration_ms,
            )

            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={output_key: result},
                duration_ms=duration_ms,
            )

        except Exception as e:
            self._logger.exception("Transform failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _safe_eval(self, expression: str, context: dict[str, Any]) -> Any:
        """Safely evaluate expression."""
        # Create restricted globals
        safe_globals = {"__builtins__": self.SAFE_BUILTINS}
        safe_globals.update(context)

        try:
            # Compile and evaluate
            code = compile(expression, "<expression>", "eval")
            return eval(code, safe_globals, {})
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}")
        except NameError as e:
            raise ValueError(f"Unknown variable in expression: {e}")


class AggregateAction(ActionBlock):
    """Aggregate data from multiple sources."""

    action_type: ClassVar[str] = "aggregate"
    category: ClassVar[ActionCategory] = ActionCategory.DATA
    display_name: ClassVar[str] = "Aggregate"
    description: ClassVar[str] = "Aggregate data from multiple sources"
    icon: ClassVar[str] = "layers"
    schema: ClassVar[ActionSchema] = ActionSchema(
        type="object",
        required=["operation"],
        properties={
            "operation": {
                "type": "string",
                "enum": ["merge", "concat", "group", "count", "sum", "average"],
                "description": "Aggregation operation",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keys to aggregate from previous outputs",
            },
            "group_by": {
                "type": "string",
                "description": "Field to group by (for group operation)",
            },
            "output_key": {
                "type": "string",
                "default": "aggregated",
                "description": "Key to store aggregated result",
            },
        },
    )

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute aggregation."""
        start_time = time.time()

        try:
            operation = self.config.get("operation", "merge")
            sources = self.config.get("sources", [])
            output_key = self.config.get("output_key", "aggregated")

            # Collect data from sources
            data = []
            for source in sources:
                if source in context.previous_outputs:
                    data.append(context.previous_outputs[source])
                elif source in context.variables:
                    data.append(context.variables[source])

            # If no sources specified, use all previous outputs
            if not sources:
                data = list(context.previous_outputs.values())

            # Perform aggregation
            if operation == "merge":
                result = self._merge(data)
            elif operation == "concat":
                result = self._concat(data)
            elif operation == "group":
                group_by = self.config.get("group_by")
                result = self._group(data, group_by)
            elif operation == "count":
                result = self._count(data)
            elif operation == "sum":
                result = self._sum(data)
            elif operation == "average":
                result = self._average(data)
            else:
                result = data

            duration_ms = (time.time() - start_time) * 1000
            return self._create_result(
                status=ActionStatus.SUCCESS,
                output={output_key: result},
                duration_ms=duration_ms,
                operation=operation,
            )

        except Exception as e:
            self._logger.exception("Aggregation failed")
            return self._create_result(
                status=ActionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _merge(self, data: list) -> dict:
        """Merge dictionaries."""
        result = {}
        for item in data:
            if isinstance(item, dict):
                result.update(item)
        return result

    def _concat(self, data: list) -> list:
        """Concatenate lists."""
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result

    def _group(self, data: list, group_by: str | None) -> dict:
        """Group items by field."""
        if not group_by:
            return {"all": data}

        groups: dict[str, list] = {}
        for item in data:
            if isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, dict):
                        key = str(sub_item.get(group_by, "unknown"))
                        groups.setdefault(key, []).append(sub_item)
            elif isinstance(item, dict):
                key = str(item.get(group_by, "unknown"))
                groups.setdefault(key, []).append(item)

        return groups

    def _count(self, data: list) -> int:
        """Count items."""
        total = 0
        for item in data:
            if isinstance(item, list):
                total += len(item)
            else:
                total += 1
        return total

    def _sum(self, data: list) -> float:
        """Sum numeric values."""
        total = 0.0
        for item in data:
            if isinstance(item, (int, float)):
                total += item
            elif isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, (int, float)):
                        total += sub_item
        return total

    def _average(self, data: list) -> float:
        """Calculate average of numeric values."""
        values = []
        for item in data:
            if isinstance(item, (int, float)):
                values.append(item)
            elif isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, (int, float)):
                        values.append(sub_item)

        if not values:
            return 0.0
        return sum(values) / len(values)
