"""Tests for data action blocks."""

import pytest
from uuid import uuid4

from aswa_agents.actions.blocks.base import ActionContext, ActionStatus
from aswa_agents.actions.blocks.data_actions import (
    SummarizeAction,
    ExtractAction,
    TransformAction,
    AggregateAction,
)


@pytest.fixture
def context():
    """Create test context."""
    return ActionContext(
        agent_id=uuid4(),
        run_id=uuid4(),
        tenant_id=uuid4(),
        trigger_data={
            "content": "This is a test document with important information.",
            "subject": "Test Subject",
        },
        variables={},
        previous_outputs={},
        secrets={},
    )


class TestSummarizeAction:
    """Tests for SummarizeAction."""

    @pytest.mark.asyncio
    async def test_summarize_success(self, context):
        """Test successful summarization."""
        action = SummarizeAction(
            action_id="sum_1",
            config={"style": "brief", "max_length": 100},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "summary" in result.output
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_summarize_custom_keys(self, context):
        """Test summarization with custom keys."""
        action = SummarizeAction(
            action_id="sum_1",
            config={
                "input_key": "content",
                "output_key": "my_summary",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "my_summary" in result.output

    @pytest.mark.asyncio
    async def test_summarize_missing_input(self, context):
        """Test summarization with missing input."""
        action = SummarizeAction(
            action_id="sum_1",
            config={"input_key": "nonexistent"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED
        assert "No input content found" in result.error

    @pytest.mark.asyncio
    async def test_summarize_with_key_points(self, context):
        """Test summarization with key points extraction."""
        action = SummarizeAction(
            action_id="sum_1",
            config={"include_key_points": True},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "key_points" in result.output

    def test_action_metadata(self):
        """Test action metadata."""
        assert SummarizeAction.action_type == "summarize"
        assert SummarizeAction.display_name == "Summarize"
        assert SummarizeAction.schema is not None


class TestExtractAction:
    """Tests for ExtractAction."""

    @pytest.mark.asyncio
    async def test_extract_entities(self, context):
        """Test entity extraction."""
        action = ExtractAction(
            action_id="ext_1",
            config={"extraction_type": "entities"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "extracted" in result.output
        assert isinstance(result.output["extracted"], list)

    @pytest.mark.asyncio
    async def test_extract_dates(self, context):
        """Test date extraction."""
        context.trigger_data["content"] = "Meeting on 2024-01-15 and 12/25/2024"

        action = ExtractAction(
            action_id="ext_1",
            config={"extraction_type": "dates"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "extracted" in result.output

    @pytest.mark.asyncio
    async def test_extract_numbers(self, context):
        """Test number extraction."""
        context.trigger_data["content"] = "Revenue was $1,234.56 with 15% growth"

        action = ExtractAction(
            action_id="ext_1",
            config={"extraction_type": "numbers"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        extracted = result.output["extracted"]
        assert len(extracted) > 0

    @pytest.mark.asyncio
    async def test_extract_action_items(self, context):
        """Test action item extraction."""
        action = ExtractAction(
            action_id="ext_1",
            config={"extraction_type": "action_items"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert isinstance(result.output["extracted"], list)

    @pytest.mark.asyncio
    async def test_extract_missing_input(self, context):
        """Test extraction with missing input."""
        action = ExtractAction(
            action_id="ext_1",
            config={"extraction_type": "entities", "input_key": "missing"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED


class TestTransformAction:
    """Tests for TransformAction."""

    @pytest.mark.asyncio
    async def test_transform_simple(self, context):
        """Test simple transformation."""
        context.variables["value"] = 10

        action = TransformAction(
            action_id="trans_1",
            config={"expression": "vars['value'] * 2"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["transformed"] == 20

    @pytest.mark.asyncio
    async def test_transform_with_trigger_data(self, context):
        """Test transformation with trigger data."""
        action = TransformAction(
            action_id="trans_1",
            config={"expression": "trigger['subject'].upper()"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["transformed"] == "TEST SUBJECT"

    @pytest.mark.asyncio
    async def test_transform_list_operations(self, context):
        """Test list transformation."""
        context.variables["items"] = [1, 2, 3, 4, 5]

        action = TransformAction(
            action_id="trans_1",
            config={"expression": "[x * 2 for x in vars['items']]"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["transformed"] == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_transform_invalid_expression(self, context):
        """Test transformation with invalid expression."""
        action = TransformAction(
            action_id="trans_1",
            config={"expression": "invalid syntax here !!!"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED

    @pytest.mark.asyncio
    async def test_transform_with_previous_output(self, context):
        """Test transformation with previous output."""
        context.previous_outputs["sum_1"] = {"summary": "Test summary"}

        action = TransformAction(
            action_id="trans_1",
            config={"expression": "len(sum_1['summary'])"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["transformed"] == 12


class TestAggregateAction:
    """Tests for AggregateAction."""

    @pytest.mark.asyncio
    async def test_aggregate_merge(self, context):
        """Test merging dictionaries."""
        context.previous_outputs = {
            "action_1": {"key1": "value1"},
            "action_2": {"key2": "value2"},
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "merge"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["aggregated"]["key1"] == "value1"
        assert result.output["aggregated"]["key2"] == "value2"

    @pytest.mark.asyncio
    async def test_aggregate_concat(self, context):
        """Test concatenating lists."""
        context.previous_outputs = {
            "action_1": [1, 2, 3],
            "action_2": [4, 5, 6],
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "concat"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["aggregated"] == [1, 2, 3, 4, 5, 6]

    @pytest.mark.asyncio
    async def test_aggregate_count(self, context):
        """Test counting items."""
        context.previous_outputs = {
            "action_1": [1, 2, 3],
            "action_2": [4, 5],
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "count"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["aggregated"] == 5

    @pytest.mark.asyncio
    async def test_aggregate_sum(self, context):
        """Test summing values."""
        context.previous_outputs = {
            "action_1": [10, 20, 30],
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "sum"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["aggregated"] == 60

    @pytest.mark.asyncio
    async def test_aggregate_average(self, context):
        """Test averaging values."""
        context.previous_outputs = {
            "action_1": [10, 20, 30],
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "average"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["aggregated"] == 20.0

    @pytest.mark.asyncio
    async def test_aggregate_group(self, context):
        """Test grouping items."""
        context.previous_outputs = {
            "action_1": [
                {"category": "A", "value": 1},
                {"category": "B", "value": 2},
                {"category": "A", "value": 3},
            ],
        }

        action = AggregateAction(
            action_id="agg_1",
            config={"operation": "group", "group_by": "category"},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert "A" in result.output["aggregated"]
        assert "B" in result.output["aggregated"]
        assert len(result.output["aggregated"]["A"]) == 2
