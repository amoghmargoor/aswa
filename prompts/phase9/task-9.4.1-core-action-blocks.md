# Task 9.4.1: Core Action Blocks

## Objective

Implement the core action blocks that form the foundation of agent workflows, including summarization, extraction, transformation, and content generation actions.

## Prerequisites

- Task 9.1.x completed (Agent Service foundation)
- LLM integration configured

## Implementation

### Step 1: Action Block Base Classes

```python
# services/agent-service/src/aswa_agents/actions/base.py
"""Base classes for action blocks."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


class ActionStatus(str, Enum):
    """Status of an action execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class ActionContext(BaseModel):
    """Context passed to action execution."""

    execution_id: UUID
    agent_id: UUID
    tenant_id: str
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    previous_outputs: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_output(self, action_id: str) -> Any:
        """Get output from a previous action."""
        return self.previous_outputs.get(action_id)

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable from context."""
        return self.variables.get(name, default)


class ActionResult(BaseModel):
    """Result of an action execution."""

    action_id: str
    status: ActionStatus
    output: Any = None
    error: str | None = None
    execution_time_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ActionStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        return self.status == ActionStatus.FAILED


class ActionBlock(ABC, Generic[T, R]):
    """
    Base class for all action blocks.

    Action blocks are the building blocks of agent workflows.
    Each block performs a specific task and can be composed together.
    """

    # Class attributes to be overridden
    action_type: str = "base"
    display_name: str = "Base Action"
    description: str = "Base action block"
    category: str = "core"

    def __init__(self, action_id: str, config: T):
        self.action_id = action_id
        self.config = config
        self._logger = logger.bind(
            action_type=self.action_type,
            action_id=action_id,
        )

    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        """
        Execute the action.

        Args:
            context: Execution context with trigger data and previous outputs

        Returns:
            ActionResult with output or error
        """
        pass

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Get JSON schema for action configuration."""
        return {}

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        """Get JSON schema for action output."""
        return {}

    def validate_config(self) -> list[str]:
        """Validate action configuration. Returns list of errors."""
        return []

    async def pre_execute(self, context: ActionContext) -> None:
        """Hook called before execute. Can be used for setup."""
        pass

    async def post_execute(
        self, context: ActionContext, result: ActionResult
    ) -> ActionResult:
        """Hook called after execute. Can modify result."""
        return result

    async def run(self, context: ActionContext) -> ActionResult:
        """Run the action with pre/post hooks."""
        import time

        start_time = time.monotonic()

        try:
            await self.pre_execute(context)
            result = await self.execute(context)
            result = await self.post_execute(context, result)

        except Exception as e:
            self._logger.error("Action execution failed", error=str(e))
            result = ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=str(e),
            )

        result.execution_time_ms = int((time.monotonic() - start_time) * 1000)
        return result
```

### Step 2: Summarize Action

```python
# services/agent-service/src/aswa_agents/actions/core/summarize.py
"""Summarization action block."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus
from aswa_agents.llm.client import LLMClient


class SummarizeStyle(str, Enum):
    """Style of summary to generate."""

    BRIEF = "brief"
    DETAILED = "detailed"
    BULLET_POINTS = "bullet_points"
    EXECUTIVE = "executive"


class SummarizeConfig(BaseModel):
    """Configuration for summarize action."""

    max_length: int = Field(default=500, ge=50, le=5000)
    style: SummarizeStyle = SummarizeStyle.BRIEF
    focus_on: str | None = None
    language: str = "english"
    include_key_points: bool = True
    input_field: str = "content"  # Field from context to summarize


class SummarizeOutput(BaseModel):
    """Output from summarize action."""

    summary: str
    key_points: list[str] = Field(default_factory=list)
    word_count: int
    original_length: int


class SummarizeAction(ActionBlock[SummarizeConfig, SummarizeOutput]):
    """
    Summarize content using LLM.

    Takes content from trigger data or previous action output
    and generates a summary based on configuration.
    """

    action_type = "summarize"
    display_name = "Summarize Content"
    description = "Generate a summary of the input content"
    category = "core"

    STYLE_PROMPTS = {
        SummarizeStyle.BRIEF: "Provide a concise summary in 2-3 sentences.",
        SummarizeStyle.DETAILED: "Provide a comprehensive summary covering all main points.",
        SummarizeStyle.BULLET_POINTS: "Provide a summary as a bulleted list of key points.",
        SummarizeStyle.EXECUTIVE: "Provide an executive summary focusing on key decisions and outcomes.",
    }

    def __init__(self, action_id: str, config: SummarizeConfig):
        super().__init__(action_id, config)
        self.llm_client = LLMClient()

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute summarization."""
        # Get content to summarize
        content = self._get_content(context)

        if not content:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"No content found in field '{self.config.input_field}'",
            )

        # Build prompt
        prompt = self._build_prompt(content)

        # Call LLM
        try:
            response = await self.llm_client.complete(
                system_prompt=self._get_system_prompt(),
                user_prompt=prompt,
                max_tokens=self.config.max_length * 2,  # Buffer for formatting
            )

            # Parse response
            summary, key_points = self._parse_response(response)

            output = SummarizeOutput(
                summary=summary,
                key_points=key_points,
                word_count=len(summary.split()),
                original_length=len(content),
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except Exception as e:
            self._logger.error("Summarization failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Summarization failed: {str(e)}",
            )

    def _get_content(self, context: ActionContext) -> str | None:
        """Get content to summarize from context."""
        # Check trigger data first
        if self.config.input_field in context.trigger_data:
            return str(context.trigger_data[self.config.input_field])

        # Check previous outputs
        for output in context.previous_outputs.values():
            if isinstance(output, dict) and self.config.input_field in output:
                return str(output[self.config.input_field])

        # Check for common content fields
        for field in ["content", "body", "text", "message"]:
            if field in context.trigger_data:
                return str(context.trigger_data[field])

        return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for summarization."""
        return """You are an expert summarizer. Your task is to create clear, accurate summaries
that capture the essential information while being easy to read.

Guidelines:
- Be accurate and faithful to the source content
- Use clear, professional language
- Focus on the most important information
- Maintain appropriate length based on the style requested"""

    def _build_prompt(self, content: str) -> str:
        """Build the summarization prompt."""
        style_instruction = self.STYLE_PROMPTS[self.config.style]

        parts = [
            f"Please summarize the following content. {style_instruction}",
        ]

        if self.config.focus_on:
            parts.append(f"\nFocus particularly on: {self.config.focus_on}")

        if self.config.language != "english":
            parts.append(f"\nProvide the summary in {self.config.language}.")

        parts.append(f"\nMaximum length: approximately {self.config.max_length} characters.")

        if self.config.include_key_points:
            parts.append("\nAlso list 3-5 key points from the content.")

        parts.append(f"\n\n---\nCONTENT:\n{content}\n---")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> tuple[str, list[str]]:
        """Parse LLM response into summary and key points."""
        key_points = []
        summary = response

        # Try to extract key points if present
        if "key points" in response.lower() or "•" in response or "- " in response:
            lines = response.split("\n")
            summary_lines = []
            in_key_points = False

            for line in lines:
                stripped = line.strip()
                if "key points" in stripped.lower():
                    in_key_points = True
                    continue

                if in_key_points and (stripped.startswith("•") or stripped.startswith("-") or stripped.startswith("*")):
                    # Remove bullet and clean
                    point = stripped.lstrip("•-* ").strip()
                    if point:
                        key_points.append(point)
                elif not in_key_points:
                    summary_lines.append(line)

            if summary_lines:
                summary = "\n".join(summary_lines).strip()

        return summary, key_points

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return SummarizeConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return SummarizeOutput.model_json_schema()
```

### Step 3: Extract Action

```python
# services/agent-service/src/aswa_agents/actions/core/extract.py
"""Data extraction action block."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus
from aswa_agents.llm.client import LLMClient


class ExtractType(str, Enum):
    """Type of data to extract."""

    ACTION_ITEMS = "action_items"
    ENTITIES = "entities"
    KEY_POINTS = "key_points"
    DATES = "dates"
    CONTACTS = "contacts"
    CUSTOM = "custom"


class ExtractConfig(BaseModel):
    """Configuration for extract action."""

    extract_type: ExtractType = ExtractType.ACTION_ITEMS
    custom_schema: dict[str, Any] | None = None
    custom_prompt: str | None = None
    input_field: str = "content"
    max_items: int = Field(default=20, ge=1, le=100)


class ExtractedItem(BaseModel):
    """A single extracted item."""

    type: str
    value: str
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractOutput(BaseModel):
    """Output from extract action."""

    items: list[ExtractedItem]
    raw_extraction: dict[str, Any] = Field(default_factory=dict)
    extraction_type: str


class ExtractAction(ActionBlock[ExtractConfig, ExtractOutput]):
    """
    Extract structured data from content.

    Supports predefined extraction types (action items, entities, etc.)
    as well as custom schema-based extraction.
    """

    action_type = "extract"
    display_name = "Extract Data"
    description = "Extract structured information from content"
    category = "core"

    EXTRACTION_PROMPTS = {
        ExtractType.ACTION_ITEMS: """Extract all action items, tasks, and to-dos from the content.
For each item, identify:
- The action to be taken
- Who is responsible (if mentioned)
- Due date (if mentioned)
- Priority (if indicated)

Return as a JSON array of objects with keys: action, assignee, due_date, priority""",

        ExtractType.ENTITIES: """Extract all named entities from the content.
Identify:
- People (names, titles, roles)
- Organizations (companies, teams, departments)
- Locations (places, addresses)
- Products/Services mentioned

Return as a JSON object with keys: people, organizations, locations, products""",

        ExtractType.KEY_POINTS: """Extract the key points and main takeaways from the content.
For each point:
- Summarize the key insight
- Note its importance (high/medium/low)
- Identify any supporting details

Return as a JSON array of objects with keys: point, importance, details""",

        ExtractType.DATES: """Extract all dates, deadlines, and time references from the content.
For each date:
- The date/time mentioned
- What event or deadline it refers to
- Whether it's a deadline, meeting, or general reference

Return as a JSON array of objects with keys: date, event, type""",

        ExtractType.CONTACTS: """Extract all contact information from the content.
For each contact:
- Name
- Email addresses
- Phone numbers
- Company/Organization
- Role/Title

Return as a JSON array of objects with keys: name, email, phone, company, role""",
    }

    def __init__(self, action_id: str, config: ExtractConfig):
        super().__init__(action_id, config)
        self.llm_client = LLMClient()

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute extraction."""
        content = self._get_content(context)

        if not content:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"No content found in field '{self.config.input_field}'",
            )

        prompt = self._build_prompt(content)

        try:
            response = await self.llm_client.complete(
                system_prompt=self._get_system_prompt(),
                user_prompt=prompt,
                max_tokens=2000,
            )

            items, raw = self._parse_response(response)

            output = ExtractOutput(
                items=items[:self.config.max_items],
                raw_extraction=raw,
                extraction_type=self.config.extract_type.value,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except Exception as e:
            self._logger.error("Extraction failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Extraction failed: {str(e)}",
            )

    def _get_content(self, context: ActionContext) -> str | None:
        """Get content to extract from."""
        if self.config.input_field in context.trigger_data:
            return str(context.trigger_data[self.config.input_field])

        for output in context.previous_outputs.values():
            if isinstance(output, dict):
                if self.config.input_field in output:
                    return str(output[self.config.input_field])
                if "summary" in output:
                    return str(output["summary"])

        for field in ["content", "body", "text"]:
            if field in context.trigger_data:
                return str(context.trigger_data[field])

        return None

    def _get_system_prompt(self) -> str:
        return """You are a precise data extraction assistant. Your task is to extract
structured information from text and return it in valid JSON format.

Guidelines:
- Extract only information that is explicitly stated
- Use null for fields that are not mentioned
- Be precise and avoid assumptions
- Always return valid JSON"""

    def _build_prompt(self, content: str) -> str:
        if self.config.extract_type == ExtractType.CUSTOM:
            if self.config.custom_prompt:
                instruction = self.config.custom_prompt
            elif self.config.custom_schema:
                instruction = f"Extract data matching this schema:\n{self.config.custom_schema}"
            else:
                instruction = "Extract key information from the content as JSON."
        else:
            instruction = self.EXTRACTION_PROMPTS[self.config.extract_type]

        return f"""{instruction}

---
CONTENT:
{content}
---

Return only valid JSON, no additional text."""

    def _parse_response(self, response: str) -> tuple[list[ExtractedItem], dict]:
        """Parse LLM response into extracted items."""
        import json

        items = []
        raw = {}

        # Clean response
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        try:
            raw = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            # Try to find JSON in response
            import re
            match = re.search(r'\{.*\}|\[.*\]', cleaned, re.DOTALL)
            if match:
                try:
                    raw = json.loads(match.group())
                except json.JSONDecodeError:
                    raw = {"raw_text": response}

        # Convert to ExtractedItem list
        items = self._convert_to_items(raw)

        return items, raw

    def _convert_to_items(self, raw: dict | list) -> list[ExtractedItem]:
        """Convert raw extraction to ExtractedItem list."""
        items = []

        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    items.append(ExtractedItem(
                        type=self.config.extract_type.value,
                        value=str(item.get("action") or item.get("point") or item.get("value") or str(item)),
                        metadata=item,
                    ))
                else:
                    items.append(ExtractedItem(
                        type=self.config.extract_type.value,
                        value=str(item),
                    ))

        elif isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, list):
                    for v in value:
                        items.append(ExtractedItem(
                            type=key,
                            value=str(v) if not isinstance(v, dict) else str(v.get("name") or v.get("value") or v),
                            metadata=v if isinstance(v, dict) else {},
                        ))
                else:
                    items.append(ExtractedItem(
                        type=key,
                        value=str(value),
                    ))

        return items

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return ExtractConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return ExtractOutput.model_json_schema()
```

### Step 4: Transform Action

```python
# services/agent-service/src/aswa_agents/actions/core/transform.py
"""Data transformation action block."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class TransformType(str, Enum):
    """Type of transformation."""

    MAP = "map"
    FILTER = "filter"
    FORMAT = "format"
    MERGE = "merge"
    SPLIT = "split"
    TEMPLATE = "template"


class TransformConfig(BaseModel):
    """Configuration for transform action."""

    transform_type: TransformType
    input_field: str = "content"
    output_field: str = "result"

    # For MAP/FILTER
    expression: str | None = None

    # For FORMAT
    format_string: str | None = None

    # For MERGE
    merge_fields: list[str] = Field(default_factory=list)
    merge_separator: str = "\n"

    # For SPLIT
    split_delimiter: str = "\n"
    split_limit: int | None = None

    # For TEMPLATE
    template: str | None = None


class TransformOutput(BaseModel):
    """Output from transform action."""

    result: Any
    input_type: str
    output_type: str
    items_processed: int = 0


class TransformAction(ActionBlock[TransformConfig, TransformOutput]):
    """
    Transform data between actions.

    Provides data manipulation capabilities including
    mapping, filtering, formatting, merging, and templating.
    """

    action_type = "transform"
    display_name = "Transform Data"
    description = "Transform and manipulate data"
    category = "core"

    def __init__(self, action_id: str, config: TransformConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute transformation."""
        input_data = self._get_input(context)

        if input_data is None:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"No input data found for field '{self.config.input_field}'",
            )

        try:
            if self.config.transform_type == TransformType.MAP:
                result = self._apply_map(input_data)
            elif self.config.transform_type == TransformType.FILTER:
                result = self._apply_filter(input_data)
            elif self.config.transform_type == TransformType.FORMAT:
                result = self._apply_format(input_data)
            elif self.config.transform_type == TransformType.MERGE:
                result = self._apply_merge(context)
            elif self.config.transform_type == TransformType.SPLIT:
                result = self._apply_split(input_data)
            elif self.config.transform_type == TransformType.TEMPLATE:
                result = self._apply_template(input_data, context)
            else:
                result = input_data

            output = TransformOutput(
                result=result,
                input_type=type(input_data).__name__,
                output_type=type(result).__name__,
                items_processed=len(result) if isinstance(result, (list, dict)) else 1,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output={self.config.output_field: result, **output.model_dump()},
            )

        except Exception as e:
            self._logger.error("Transform failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Transform failed: {str(e)}",
            )

    def _get_input(self, context: ActionContext) -> Any:
        """Get input data from context."""
        # Check previous outputs
        for action_id, output in context.previous_outputs.items():
            if isinstance(output, dict):
                if self.config.input_field in output:
                    return output[self.config.input_field]
                if "result" in output:
                    return output["result"]

        # Check trigger data
        if self.config.input_field in context.trigger_data:
            return context.trigger_data[self.config.input_field]

        # Check variables
        if self.config.input_field in context.variables:
            return context.variables[self.config.input_field]

        return None

    def _apply_map(self, data: Any) -> Any:
        """Apply map transformation."""
        if not self.config.expression:
            return data

        if isinstance(data, list):
            return [self._evaluate_expression(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._evaluate_expression(v) for k, v in data.items()}
        else:
            return self._evaluate_expression(data)

    def _apply_filter(self, data: Any) -> Any:
        """Apply filter transformation."""
        if not self.config.expression or not isinstance(data, list):
            return data

        return [item for item in data if self._evaluate_condition(item)]

    def _apply_format(self, data: Any) -> str:
        """Apply format transformation."""
        if not self.config.format_string:
            return str(data)

        if isinstance(data, dict):
            return self.config.format_string.format(**data)
        elif isinstance(data, list):
            return self.config.format_string.format(*data)
        else:
            return self.config.format_string.format(value=data)

    def _apply_merge(self, context: ActionContext) -> str:
        """Merge multiple fields."""
        parts = []

        for field in self.config.merge_fields:
            value = None

            # Check previous outputs
            for output in context.previous_outputs.values():
                if isinstance(output, dict) and field in output:
                    value = output[field]
                    break

            # Check trigger data
            if value is None and field in context.trigger_data:
                value = context.trigger_data[field]

            if value is not None:
                parts.append(str(value))

        return self.config.merge_separator.join(parts)

    def _apply_split(self, data: Any) -> list[str]:
        """Split string into list."""
        if not isinstance(data, str):
            data = str(data)

        parts = data.split(self.config.split_delimiter)

        if self.config.split_limit:
            parts = parts[:self.config.split_limit]

        return [p.strip() for p in parts if p.strip()]

    def _apply_template(self, data: Any, context: ActionContext) -> str:
        """Apply template transformation."""
        if not self.config.template:
            return str(data)

        # Build template context
        template_vars = {
            "input": data,
            "trigger": context.trigger_data,
            "outputs": context.previous_outputs,
            "vars": context.variables,
        }

        if isinstance(data, dict):
            template_vars.update(data)

        # Simple template substitution
        result = self.config.template
        for key, value in template_vars.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    result = result.replace(f"{{{{{key}.{k}}}}}", str(v))
            result = result.replace(f"{{{{{key}}}}}", str(value))

        return result

    def _evaluate_expression(self, item: Any) -> Any:
        """Safely evaluate a mapping expression."""
        if not self.config.expression:
            return item

        # Simple property access
        expr = self.config.expression
        if expr.startswith("item.") and isinstance(item, dict):
            key = expr[5:]
            return item.get(key, item)

        return item

    def _evaluate_condition(self, item: Any) -> bool:
        """Safely evaluate a filter condition."""
        if not self.config.expression:
            return True

        expr = self.config.expression

        # Simple comparisons
        if isinstance(item, dict):
            for key, value in item.items():
                if f"{key} ==" in expr:
                    expected = expr.split(f"{key} ==")[1].strip().strip("'\"")
                    if str(value) == expected:
                        return True
                if f"{key} !=" in expr:
                    expected = expr.split(f"{key} !=")[1].strip().strip("'\"")
                    if str(value) != expected:
                        return True

        return bool(item)

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return TransformConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return TransformOutput.model_json_schema()
```

### Step 5: Query Knowledge Action

```python
# services/agent-service/src/aswa_agents/actions/core/query_knowledge.py
"""Query knowledge base action block."""

from typing import Any

from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionBlock, ActionContext, ActionResult, ActionStatus


class QueryKnowledgeConfig(BaseModel):
    """Configuration for query knowledge action."""

    query_field: str = "query"  # Field containing query
    auto_generate_query: bool = True  # Generate query from content
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.7, ge=0, le=1)
    include_metadata: bool = True
    collection: str | None = None  # Specific collection to query


class QueryResult(BaseModel):
    """A single query result."""

    content: str
    similarity: float
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryKnowledgeOutput(BaseModel):
    """Output from query knowledge action."""

    query: str
    results: list[QueryResult]
    total_results: int
    has_relevant_results: bool


class QueryKnowledgeAction(ActionBlock[QueryKnowledgeConfig, QueryKnowledgeOutput]):
    """
    Query the ASWA knowledge base.

    Integrates with the existing query-service to retrieve
    relevant documents and context.
    """

    action_type = "query_knowledge"
    display_name = "Query Knowledge Base"
    description = "Search the knowledge base for relevant information"
    category = "core"

    def __init__(self, action_id: str, config: QueryKnowledgeConfig):
        super().__init__(action_id, config)

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute knowledge query."""
        # Get or generate query
        query = await self._get_query(context)

        if not query:
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error="No query could be generated or found",
            )

        try:
            # Call query service
            results = await self._query_knowledge_base(query, context.tenant_id)

            # Filter by similarity
            filtered = [
                r for r in results
                if r.similarity >= self.config.min_similarity
            ][:self.config.top_k]

            output = QueryKnowledgeOutput(
                query=query,
                results=filtered,
                total_results=len(results),
                has_relevant_results=len(filtered) > 0,
            )

            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.COMPLETED,
                output=output.model_dump(),
            )

        except Exception as e:
            self._logger.error("Knowledge query failed", error=str(e))
            return ActionResult(
                action_id=self.action_id,
                status=ActionStatus.FAILED,
                error=f"Query failed: {str(e)}",
            )

    async def _get_query(self, context: ActionContext) -> str | None:
        """Get query string from context or generate it."""
        # Check for explicit query
        if self.config.query_field in context.trigger_data:
            return str(context.trigger_data[self.config.query_field])

        for output in context.previous_outputs.values():
            if isinstance(output, dict) and self.config.query_field in output:
                return str(output[self.config.query_field])

        # Auto-generate query from content
        if self.config.auto_generate_query:
            content = None
            for field in ["content", "body", "text", "summary"]:
                if field in context.trigger_data:
                    content = str(context.trigger_data[field])
                    break

            if content:
                return await self._generate_query(content)

        return None

    async def _generate_query(self, content: str) -> str:
        """Generate a search query from content."""
        from aswa_agents.llm.client import LLMClient

        llm = LLMClient()

        response = await llm.complete(
            system_prompt="Generate a concise search query (max 100 chars) to find relevant information for the given content. Return only the query, nothing else.",
            user_prompt=f"Content:\n{content[:1000]}",
            max_tokens=100,
        )

        return response.strip()

    async def _query_knowledge_base(
        self, query: str, tenant_id: str
    ) -> list[QueryResult]:
        """Query the knowledge base via query-service."""
        import httpx

        # Call query-service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://query-service:8000/api/v1/query",
                json={
                    "query": query,
                    "tenant_id": tenant_id,
                    "top_k": self.config.top_k * 2,  # Get extra for filtering
                    "collection": self.config.collection,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for doc in data.get("documents", []):
            results.append(QueryResult(
                content=doc.get("content", ""),
                similarity=doc.get("score", 0.0),
                source=doc.get("source", "unknown"),
                metadata=doc.get("metadata", {}) if self.config.include_metadata else {},
            ))

        return results

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        return QueryKnowledgeConfig.model_json_schema()

    @classmethod
    def get_output_schema(cls) -> dict[str, Any]:
        return QueryKnowledgeOutput.model_json_schema()
```

## Test Cases

```python
# services/agent-service/tests/unit/test_core_actions.py
"""Tests for core action blocks."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_agents.actions.base import ActionContext, ActionStatus
from aswa_agents.actions.core.summarize import SummarizeAction, SummarizeConfig, SummarizeStyle
from aswa_agents.actions.core.extract import ExtractAction, ExtractConfig, ExtractType
from aswa_agents.actions.core.transform import TransformAction, TransformConfig, TransformType
from aswa_agents.actions.core.query_knowledge import QueryKnowledgeAction, QueryKnowledgeConfig


@pytest.fixture
def context():
    """Create test context."""
    return ActionContext(
        execution_id=uuid4(),
        agent_id=uuid4(),
        tenant_id="test-tenant",
        trigger_data={
            "content": "This is a test document about AI and machine learning. "
                       "Action item: Review the proposal by Friday. "
                       "Contact: john@example.com for more info.",
            "subject": "Test Email",
        },
    )


class TestSummarizeAction:
    """Test SummarizeAction."""

    @pytest.mark.asyncio
    async def test_summarize_brief(self, context):
        """Test brief summarization."""
        config = SummarizeConfig(style=SummarizeStyle.BRIEF, max_length=100)
        action = SummarizeAction("test-summarize", config)

        with patch.object(action.llm_client, "complete", new_callable=AsyncMock) as mock:
            mock.return_value = "This is a brief summary about AI and ML."

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert "summary" in result.output
            assert len(result.output["summary"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_with_key_points(self, context):
        """Test summarization with key points."""
        config = SummarizeConfig(
            style=SummarizeStyle.BULLET_POINTS,
            include_key_points=True,
        )
        action = SummarizeAction("test-summarize", config)

        with patch.object(action.llm_client, "complete", new_callable=AsyncMock) as mock:
            mock.return_value = """Summary of the document.

Key Points:
• AI and ML are discussed
• Action item to review proposal
• Contact information provided"""

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert "key_points" in result.output
            assert len(result.output["key_points"]) >= 1

    @pytest.mark.asyncio
    async def test_summarize_missing_content(self, context):
        """Test summarization with missing content."""
        context.trigger_data = {}
        config = SummarizeConfig()
        action = SummarizeAction("test-summarize", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED
        assert "No content found" in result.error


class TestExtractAction:
    """Test ExtractAction."""

    @pytest.mark.asyncio
    async def test_extract_action_items(self, context):
        """Test action item extraction."""
        config = ExtractConfig(extract_type=ExtractType.ACTION_ITEMS)
        action = ExtractAction("test-extract", config)

        with patch.object(action.llm_client, "complete", new_callable=AsyncMock) as mock:
            mock.return_value = """[
                {"action": "Review the proposal", "assignee": null, "due_date": "Friday", "priority": "medium"}
            ]"""

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert "items" in result.output
            assert len(result.output["items"]) >= 1

    @pytest.mark.asyncio
    async def test_extract_entities(self, context):
        """Test entity extraction."""
        config = ExtractConfig(extract_type=ExtractType.ENTITIES)
        action = ExtractAction("test-extract", config)

        with patch.object(action.llm_client, "complete", new_callable=AsyncMock) as mock:
            mock.return_value = """{
                "people": [{"name": "John", "email": "john@example.com"}],
                "organizations": [],
                "locations": []
            }"""

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert "raw_extraction" in result.output

    @pytest.mark.asyncio
    async def test_extract_contacts(self, context):
        """Test contact extraction."""
        config = ExtractConfig(extract_type=ExtractType.CONTACTS)
        action = ExtractAction("test-extract", config)

        with patch.object(action.llm_client, "complete", new_callable=AsyncMock) as mock:
            mock.return_value = """[
                {"name": "John", "email": "john@example.com", "phone": null, "company": null, "role": null}
            ]"""

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            items = result.output["items"]
            assert any("john@example.com" in str(item) for item in items)


class TestTransformAction:
    """Test TransformAction."""

    @pytest.mark.asyncio
    async def test_transform_split(self, context):
        """Test split transformation."""
        context.trigger_data["content"] = "item1\nitem2\nitem3"
        config = TransformConfig(
            transform_type=TransformType.SPLIT,
            split_delimiter="\n",
        )
        action = TransformAction("test-transform", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert len(result.output["result"]) == 3

    @pytest.mark.asyncio
    async def test_transform_format(self, context):
        """Test format transformation."""
        context.trigger_data = {"name": "John", "email": "john@example.com"}
        config = TransformConfig(
            transform_type=TransformType.FORMAT,
            input_field="name",
            format_string="Hello {value}!",
        )
        action = TransformAction("test-transform", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert "Hello John!" in result.output["result"]

    @pytest.mark.asyncio
    async def test_transform_template(self, context):
        """Test template transformation."""
        context.trigger_data = {"user": "Alice", "message": "Hello"}
        config = TransformConfig(
            transform_type=TransformType.TEMPLATE,
            input_field="user",
            template="User {{input}} says: {{trigger.message}}",
        )
        action = TransformAction("test-transform", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert "Alice" in result.output["result"]

    @pytest.mark.asyncio
    async def test_transform_merge(self, context):
        """Test merge transformation."""
        context.trigger_data = {
            "field1": "Hello",
            "field2": "World",
        }
        config = TransformConfig(
            transform_type=TransformType.MERGE,
            merge_fields=["field1", "field2"],
            merge_separator=" ",
        )
        action = TransformAction("test-transform", config)

        result = await action.execute(context)

        assert result.status == ActionStatus.COMPLETED
        assert result.output["result"] == "Hello World"


class TestQueryKnowledgeAction:
    """Test QueryKnowledgeAction."""

    @pytest.mark.asyncio
    async def test_query_with_explicit_query(self, context):
        """Test query with explicit query field."""
        context.trigger_data["query"] = "What is machine learning?"
        config = QueryKnowledgeConfig(query_field="query")
        action = QueryKnowledgeAction("test-query", config)

        with patch.object(action, "_query_knowledge_base", new_callable=AsyncMock) as mock:
            from aswa_agents.actions.core.query_knowledge import QueryResult
            mock.return_value = [
                QueryResult(
                    content="Machine learning is...",
                    similarity=0.9,
                    source="doc1.pdf",
                )
            ]

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert result.output["has_relevant_results"] is True

    @pytest.mark.asyncio
    async def test_query_auto_generate(self, context):
        """Test query with auto-generated query."""
        config = QueryKnowledgeConfig(auto_generate_query=True)
        action = QueryKnowledgeAction("test-query", config)

        with patch.object(action, "_generate_query", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "AI machine learning overview"

            with patch.object(action, "_query_knowledge_base", new_callable=AsyncMock) as mock_query:
                from aswa_agents.actions.core.query_knowledge import QueryResult
                mock_query.return_value = [
                    QueryResult(content="...", similarity=0.8, source="doc.pdf")
                ]

                result = await action.execute(context)

                assert result.status == ActionStatus.COMPLETED
                mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_filters_by_similarity(self, context):
        """Test that results are filtered by min similarity."""
        context.trigger_data["query"] = "test query"
        config = QueryKnowledgeConfig(min_similarity=0.8)
        action = QueryKnowledgeAction("test-query", config)

        with patch.object(action, "_query_knowledge_base", new_callable=AsyncMock) as mock:
            from aswa_agents.actions.core.query_knowledge import QueryResult
            mock.return_value = [
                QueryResult(content="High", similarity=0.9, source="a"),
                QueryResult(content="Low", similarity=0.5, source="b"),
            ]

            result = await action.execute(context)

            assert result.status == ActionStatus.COMPLETED
            assert len(result.output["results"]) == 1
            assert result.output["results"][0]["similarity"] == 0.9
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_core_actions.py -v
   ```

2. **Test action execution:**
   ```python
   from aswa_agents.actions.core.summarize import SummarizeAction, SummarizeConfig
   from aswa_agents.actions.base import ActionContext
   from uuid import uuid4

   config = SummarizeConfig(max_length=200)
   action = SummarizeAction("test", config)

   context = ActionContext(
       execution_id=uuid4(),
       agent_id=uuid4(),
       tenant_id="test",
       trigger_data={"content": "Your test content here..."}
   )

   result = await action.run(context)
   print(result.output)
   ```

3. **Verify action schemas:**
   ```python
   from aswa_agents.actions.core.summarize import SummarizeAction
   print(SummarizeAction.get_config_schema())
   print(SummarizeAction.get_output_schema())
   ```

## Next Task

Proceed to `task-9.4.2-integration-action-blocks.md` for implementing integration action blocks (Slack, Email, Tickets).
