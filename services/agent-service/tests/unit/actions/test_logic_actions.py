"""Tests for logic action blocks."""

import pytest
from uuid import uuid4

from aswa_agents.actions.blocks.base import ActionContext, ActionStatus
from aswa_agents.actions.blocks.logic_actions import (
    FilterAction,
    BranchAction,
    LoopAction,
    DelayAction,
)


@pytest.fixture
def context():
    """Create test context."""
    return ActionContext(
        agent_id=uuid4(),
        run_id=uuid4(),
        tenant_id=uuid4(),
        trigger_data={
            "confidence": 0.9,
            "sender": "user@company.com",
            "subject": "Urgent: Action required",
        },
        variables={},
        previous_outputs={},
        secrets={},
    )


class TestFilterAction:
    """Tests for FilterAction."""

    @pytest.mark.asyncio
    async def test_filter_expression_true(self, context):
        """Test filter with matching expression."""
        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "confidence > 0.8",
                "on_match": "continue",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["matched"] is True

    @pytest.mark.asyncio
    async def test_filter_expression_false(self, context):
        """Test filter with non-matching expression."""
        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "confidence > 0.95",
                "on_match": "continue",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SKIPPED
        assert result.output["matched"] is False

    @pytest.mark.asyncio
    async def test_filter_skip_on_match(self, context):
        """Test filter with skip on match."""
        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "confidence > 0.8",
                "on_match": "skip",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_filter_array(self, context):
        """Test filtering array items."""
        context.previous_outputs["source"] = {
            "items": [
                {"name": "item1", "value": 10},
                {"name": "item2", "value": 50},
                {"name": "item3", "value": 30},
            ]
        }

        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "value > 20",
                "input_key": "items",
                "output_key": "high_value",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert len(result.output["high_value"]) == 2

    @pytest.mark.asyncio
    async def test_filter_string_contains(self, context):
        """Test filter with string operations."""
        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "'urgent' in subject.lower()",
                "on_match": "continue",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["matched"] is True

    @pytest.mark.asyncio
    async def test_filter_invalid_expression(self, context):
        """Test filter with invalid expression."""
        action = FilterAction(
            action_id="filter_1",
            config={
                "expression": "undefined_var > 10",
                "on_match": "continue",
            },
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SKIPPED
        assert result.output["matched"] is False


class TestBranchAction:
    """Tests for BranchAction."""

    @pytest.mark.asyncio
    async def test_branch_first_condition(self, context):
        """Test branch with first condition matching."""
        action = BranchAction(
            action_id="branch_1",
            config={
                "conditions": [
                    {"expression": "confidence > 0.8", "actions": []},
                    {"expression": "confidence > 0.5", "actions": []},
                ],
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["matched_branch"] == 0
        assert result.output["branch_taken"] == "conditional"

    @pytest.mark.asyncio
    async def test_branch_second_condition(self, context):
        """Test branch with second condition matching."""
        context.trigger_data["confidence"] = 0.7

        action = BranchAction(
            action_id="branch_1",
            config={
                "conditions": [
                    {"expression": "confidence > 0.8", "actions": []},
                    {"expression": "confidence > 0.5", "actions": []},
                ],
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["matched_branch"] == 1

    @pytest.mark.asyncio
    async def test_branch_default(self, context):
        """Test branch falling through to default."""
        context.trigger_data["confidence"] = 0.3

        action = BranchAction(
            action_id="branch_1",
            config={
                "conditions": [
                    {"expression": "confidence > 0.8", "actions": []},
                    {"expression": "confidence > 0.5", "actions": []},
                ],
                "default_actions": [],
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["matched_branch"] is None
        assert result.output["branch_taken"] == "default"


class TestLoopAction:
    """Tests for LoopAction."""

    @pytest.mark.asyncio
    async def test_loop_over_items(self, context):
        """Test looping over items."""
        context.previous_outputs["source"] = {
            "items": [1, 2, 3, 4, 5]
        }

        action = LoopAction(
            action_id="loop_1",
            config={
                "items_key": "items",
                "item_variable": "current",
                "output_key": "results",
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["item_count"] == 5
        assert len(result.output["results"]) == 5

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self, context):
        """Test loop with max iterations limit."""
        context.previous_outputs["source"] = {
            "items": list(range(1000))
        }

        action = LoopAction(
            action_id="loop_1",
            config={
                "items_key": "items",
                "max_iterations": 10,
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["item_count"] == 10

    @pytest.mark.asyncio
    async def test_loop_missing_items(self, context):
        """Test loop with missing items key."""
        action = LoopAction(
            action_id="loop_1",
            config={
                "items_key": "nonexistent",
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED

    @pytest.mark.asyncio
    async def test_loop_not_array(self, context):
        """Test loop with non-array input."""
        context.variables["items"] = "not an array"

        action = LoopAction(
            action_id="loop_1",
            config={
                "items_key": "items",
            },
            children=[],
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.FAILED


class TestDelayAction:
    """Tests for DelayAction."""

    @pytest.mark.asyncio
    async def test_delay_zero(self, context):
        """Test delay with zero duration."""
        action = DelayAction(
            action_id="delay_1",
            config={"duration": 0},
        )

        result = await action.execute(context)

        assert result.status == ActionStatus.SUCCESS
        assert result.output["delayed_seconds"] == 0

    @pytest.mark.asyncio
    async def test_delay_short(self, context):
        """Test short delay."""
        import time

        action = DelayAction(
            action_id="delay_1",
            config={"duration": 0.1},
        )

        start = time.time()
        result = await action.execute(context)
        elapsed = time.time() - start

        assert result.status == ActionStatus.SUCCESS
        assert elapsed >= 0.1

    def test_action_metadata(self):
        """Test action metadata."""
        assert DelayAction.action_type == "delay"
        assert DelayAction.display_name == "Delay"
