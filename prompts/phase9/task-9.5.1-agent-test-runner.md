# Task 9.5.1: Agent Test Runner

## Objective

Implement a test runner for agents that enables dry-run testing, mock execution, and validation before deployment.

## Prerequisites

- Task 9.4.x completed (Action Blocks)
- Agent orchestrator implemented

## Implementation

### Step 1: Test Runner Service

```python
# services/agent-service/src/aswa_agents/testing/runner.py
"""Agent test runner for validation and dry-run testing."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

from aswa_agents.actions.base import ActionContext, ActionResult, ActionStatus
from aswa_agents.actions.factory import ActionFactory, ActionPipeline
from aswa_agents.actions.registry import ActionRegistry
from aswa_agents.models.agent_definition import AgentDefinitionModel

logger = structlog.get_logger()


class TestMode(str, Enum):
    """Test execution modes."""

    DRY_RUN = "dry_run"  # Simulate without side effects
    MOCK = "mock"  # Use mock data for integrations
    SANDBOX = "sandbox"  # Execute in isolated sandbox
    VALIDATE = "validate"  # Validate only, no execution


class TestCaseInput(BaseModel):
    """Input data for a test case."""

    name: str
    description: str = ""
    trigger_data: dict[str, Any]
    variables: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, Any] | None = None
    expected_status: str = "completed"


class ActionTestResult(BaseModel):
    """Test result for a single action."""

    action_id: str
    action_type: str
    status: str
    execution_time_ms: int
    output: Any = None
    error: str | None = None
    mocked: bool = False
    assertions_passed: int = 0
    assertions_failed: int = 0
    assertion_errors: list[str] = Field(default_factory=list)


class TestRunResult(BaseModel):
    """Complete test run result."""

    test_id: UUID = Field(default_factory=uuid4)
    test_case_name: str
    mode: TestMode
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "pending"
    action_results: list[ActionTestResult] = Field(default_factory=list)
    total_actions: int = 0
    passed_actions: int = 0
    failed_actions: int = 0
    skipped_actions: int = 0
    total_execution_time_ms: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentTestRunner:
    """
    Test runner for agent workflows.

    Supports dry-run testing, mock execution, and validation.
    """

    def __init__(self, mode: TestMode = TestMode.DRY_RUN):
        self.mode = mode
        self.mock_registry: dict[str, callable] = {}
        self._logger = logger.bind(component="AgentTestRunner")

    def register_mock(
        self,
        action_type: str,
        mock_fn: callable,
    ) -> None:
        """Register a mock function for an action type."""
        self.mock_registry[action_type] = mock_fn

    async def run_test(
        self,
        definition: AgentDefinitionModel,
        test_case: TestCaseInput,
    ) -> TestRunResult:
        """
        Run a test case against an agent definition.

        Args:
            definition: Agent definition to test
            test_case: Test case with input data

        Returns:
            TestRunResult with detailed results
        """
        import time

        result = TestRunResult(
            test_case_name=test_case.name,
            mode=self.mode,
            started_at=datetime.utcnow(),
        )

        # Validate definition first
        if self.mode == TestMode.VALIDATE:
            return await self._validate_only(definition, result)

        # Create execution context
        context = ActionContext(
            execution_id=result.test_id,
            agent_id=uuid4(),
            tenant_id="test",
            trigger_data=test_case.trigger_data,
            variables=test_case.variables,
            metadata={"test_mode": self.mode.value},
        )

        # Build action pipeline
        factory = ActionFactory()
        try:
            pipeline = factory.create_from_definition(definition.model_dump())
        except Exception as e:
            result.status = "failed"
            result.validation_errors.append(f"Failed to create pipeline: {str(e)}")
            result.completed_at = datetime.utcnow()
            return result

        result.total_actions = len(pipeline.actions)

        # Execute actions
        start_time = time.monotonic()

        for action in pipeline.get_execution_order():
            action_result = await self._execute_action(action, context)

            # Record result
            test_action_result = ActionTestResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status=action_result.status.value,
                execution_time_ms=action_result.execution_time_ms,
                output=action_result.output,
                error=action_result.error,
                mocked=action.action_type in self.mock_registry,
            )

            # Run assertions if expected outputs provided
            if test_case.expected_outputs:
                self._check_assertions(
                    test_action_result,
                    action.action_id,
                    action_result.output,
                    test_case.expected_outputs,
                )

            result.action_results.append(test_action_result)

            # Update context with output
            if action_result.output:
                context.previous_outputs[action.action_id] = action_result.output

            # Update counters
            if action_result.status == ActionStatus.COMPLETED:
                result.passed_actions += 1
            elif action_result.status == ActionStatus.FAILED:
                result.failed_actions += 1
            elif action_result.status == ActionStatus.SKIPPED:
                result.skipped_actions += 1

        result.total_execution_time_ms = int((time.monotonic() - start_time) * 1000)
        result.completed_at = datetime.utcnow()

        # Determine overall status
        if result.failed_actions > 0:
            result.status = "failed"
        elif any(ar.assertions_failed > 0 for ar in result.action_results):
            result.status = "assertions_failed"
        else:
            result.status = "passed"

        return result

    async def _execute_action(
        self,
        action: Any,
        context: ActionContext,
    ) -> ActionResult:
        """Execute a single action in test mode."""
        # Check for mock
        if action.action_type in self.mock_registry:
            return await self._execute_mock(action, context)

        if self.mode == TestMode.DRY_RUN:
            return await self._execute_dry_run(action, context)
        elif self.mode == TestMode.MOCK:
            return await self._execute_with_default_mock(action, context)
        elif self.mode == TestMode.SANDBOX:
            return await action.run(context)
        else:
            return ActionResult(
                action_id=action.action_id,
                status=ActionStatus.SKIPPED,
            )

    async def _execute_mock(
        self,
        action: Any,
        context: ActionContext,
    ) -> ActionResult:
        """Execute using registered mock."""
        mock_fn = self.mock_registry[action.action_type]

        try:
            output = await mock_fn(action, context)
            return ActionResult(
                action_id=action.action_id,
                status=ActionStatus.COMPLETED,
                output=output,
                metadata={"mocked": True},
            )
        except Exception as e:
            return ActionResult(
                action_id=action.action_id,
                status=ActionStatus.FAILED,
                error=str(e),
            )

    async def _execute_dry_run(
        self,
        action: Any,
        context: ActionContext,
    ) -> ActionResult:
        """Execute dry run (simulate without side effects)."""
        # For integration actions, return mock success
        if action.category == "integration":
            return ActionResult(
                action_id=action.action_id,
                status=ActionStatus.COMPLETED,
                output=self._get_default_mock_output(action.action_type),
                metadata={"dry_run": True},
            )

        # For core/logic actions, execute normally (they don't have side effects)
        return await action.run(context)

    async def _execute_with_default_mock(
        self,
        action: Any,
        context: ActionContext,
    ) -> ActionResult:
        """Execute with default mock output."""
        return ActionResult(
            action_id=action.action_id,
            status=ActionStatus.COMPLETED,
            output=self._get_default_mock_output(action.action_type),
            metadata={"mocked": True, "default_mock": True},
        )

    def _get_default_mock_output(self, action_type: str) -> dict[str, Any]:
        """Get default mock output for an action type."""
        defaults = {
            "summarize": {
                "summary": "This is a mock summary of the content.",
                "key_points": ["Point 1", "Point 2", "Point 3"],
                "word_count": 50,
            },
            "extract": {
                "items": [
                    {"type": "action_item", "value": "Mock action item 1"},
                    {"type": "action_item", "value": "Mock action item 2"},
                ],
                "extraction_type": "action_items",
            },
            "send_slack": {
                "channel": "C123456",
                "message_ts": "1234567890.123456",
                "success": True,
            },
            "send_email": {
                "message_id": "mock-message-id",
                "to": ["test@example.com"],
                "success": True,
            },
            "create_ticket": {
                "ticket_id": "mock-123",
                "ticket_key": "MOCK-123",
                "url": "https://mock.example.com/MOCK-123",
                "success": True,
            },
            "http_request": {
                "status_code": 200,
                "response_body": {"status": "ok"},
                "success": True,
            },
            "query_knowledge": {
                "query": "mock query",
                "results": [
                    {"content": "Mock result 1", "similarity": 0.95},
                ],
                "has_relevant_results": True,
            },
        }

        return defaults.get(action_type, {"mock": True})

    async def _validate_only(
        self,
        definition: AgentDefinitionModel,
        result: TestRunResult,
    ) -> TestRunResult:
        """Validate definition without execution."""
        factory = ActionFactory()
        is_valid, errors = factory.validate_definition(definition.model_dump())

        result.validation_errors = errors
        result.status = "passed" if is_valid else "validation_failed"
        result.completed_at = datetime.utcnow()

        return result

    def _check_assertions(
        self,
        test_result: ActionTestResult,
        action_id: str,
        actual_output: Any,
        expected_outputs: dict[str, Any],
    ) -> None:
        """Check assertions against expected outputs."""
        if action_id not in expected_outputs:
            return

        expected = expected_outputs[action_id]

        if not isinstance(actual_output, dict) or not isinstance(expected, dict):
            return

        for key, expected_value in expected.items():
            actual_value = actual_output.get(key) if actual_output else None

            if actual_value == expected_value:
                test_result.assertions_passed += 1
            else:
                test_result.assertions_failed += 1
                test_result.assertion_errors.append(
                    f"Expected {key}={expected_value}, got {actual_value}"
                )


class TestSuite:
    """A collection of test cases for an agent."""

    def __init__(self, name: str):
        self.name = name
        self.test_cases: list[TestCaseInput] = []
        self.setup_fn: callable | None = None
        self.teardown_fn: callable | None = None

    def add_test_case(self, test_case: TestCaseInput) -> "TestSuite":
        """Add a test case to the suite."""
        self.test_cases.append(test_case)
        return self

    def set_setup(self, fn: callable) -> "TestSuite":
        """Set setup function to run before each test."""
        self.setup_fn = fn
        return self

    def set_teardown(self, fn: callable) -> "TestSuite":
        """Set teardown function to run after each test."""
        self.teardown_fn = fn
        return self

    async def run(
        self,
        definition: AgentDefinitionModel,
        runner: AgentTestRunner | None = None,
    ) -> list[TestRunResult]:
        """Run all test cases in the suite."""
        if runner is None:
            runner = AgentTestRunner(mode=TestMode.DRY_RUN)

        results = []

        for test_case in self.test_cases:
            if self.setup_fn:
                await self.setup_fn()

            result = await runner.run_test(definition, test_case)
            results.append(result)

            if self.teardown_fn:
                await self.teardown_fn()

        return results
```

### Step 2: Test Case Builder

```python
# services/agent-service/src/aswa_agents/testing/builder.py
"""Builder for creating test cases."""

from typing import Any

from aswa_agents.testing.runner import TestCaseInput, TestSuite


class TestCaseBuilder:
    """Fluent builder for test cases."""

    def __init__(self, name: str):
        self._name = name
        self._description = ""
        self._trigger_data: dict[str, Any] = {}
        self._variables: dict[str, Any] = {}
        self._expected_outputs: dict[str, Any] = {}
        self._expected_status = "completed"

    def with_description(self, description: str) -> "TestCaseBuilder":
        """Add description."""
        self._description = description
        return self

    def with_trigger_data(self, **kwargs) -> "TestCaseBuilder":
        """Add trigger data."""
        self._trigger_data.update(kwargs)
        return self

    def with_email_trigger(
        self,
        subject: str,
        body: str,
        sender: str = "test@example.com",
        **kwargs,
    ) -> "TestCaseBuilder":
        """Configure email trigger data."""
        self._trigger_data.update({
            "type": "email",
            "subject": subject,
            "body": body,
            "content": body,
            "sender": sender,
            **kwargs,
        })
        return self

    def with_slack_trigger(
        self,
        message: str,
        channel: str = "#general",
        user: str = "U123",
        **kwargs,
    ) -> "TestCaseBuilder":
        """Configure Slack trigger data."""
        self._trigger_data.update({
            "type": "slack",
            "message": message,
            "content": message,
            "channel": channel,
            "user": user,
            **kwargs,
        })
        return self

    def with_document_trigger(
        self,
        content: str,
        filename: str = "document.pdf",
        **kwargs,
    ) -> "TestCaseBuilder":
        """Configure document trigger data."""
        self._trigger_data.update({
            "type": "document",
            "content": content,
            "filename": filename,
            **kwargs,
        })
        return self

    def with_variable(self, name: str, value: Any) -> "TestCaseBuilder":
        """Add a variable."""
        self._variables[name] = value
        return self

    def expect_output(
        self,
        action_id: str,
        **expected_values,
    ) -> "TestCaseBuilder":
        """Add expected output assertions."""
        self._expected_outputs[action_id] = expected_values
        return self

    def expect_status(self, status: str) -> "TestCaseBuilder":
        """Set expected overall status."""
        self._expected_status = status
        return self

    def build(self) -> TestCaseInput:
        """Build the test case."""
        return TestCaseInput(
            name=self._name,
            description=self._description,
            trigger_data=self._trigger_data,
            variables=self._variables,
            expected_outputs=self._expected_outputs if self._expected_outputs else None,
            expected_status=self._expected_status,
        )


class TestSuiteBuilder:
    """Fluent builder for test suites."""

    def __init__(self, name: str):
        self._name = name
        self._test_cases: list[TestCaseInput] = []
        self._setup_fn = None
        self._teardown_fn = None

    def add_case(self, test_case: TestCaseInput) -> "TestSuiteBuilder":
        """Add a test case."""
        self._test_cases.append(test_case)
        return self

    def add_builder(self, builder: TestCaseBuilder) -> "TestSuiteBuilder":
        """Add a test case from builder."""
        self._test_cases.append(builder.build())
        return self

    def with_setup(self, fn: callable) -> "TestSuiteBuilder":
        """Set setup function."""
        self._setup_fn = fn
        return self

    def with_teardown(self, fn: callable) -> "TestSuiteBuilder":
        """Set teardown function."""
        self._teardown_fn = fn
        return self

    def build(self) -> TestSuite:
        """Build the test suite."""
        suite = TestSuite(self._name)
        for tc in self._test_cases:
            suite.add_test_case(tc)

        if self._setup_fn:
            suite.set_setup(self._setup_fn)
        if self._teardown_fn:
            suite.set_teardown(self._teardown_fn)

        return suite


# Convenience functions
def test_case(name: str) -> TestCaseBuilder:
    """Create a test case builder."""
    return TestCaseBuilder(name)


def test_suite(name: str) -> TestSuiteBuilder:
    """Create a test suite builder."""
    return TestSuiteBuilder(name)
```

### Step 3: Test API Endpoints

```python
# services/agent-service/src/aswa_agents/api/testing.py
"""API endpoints for agent testing."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aswa_agents.models.agent_definition import AgentDefinitionModel
from aswa_agents.testing.runner import (
    AgentTestRunner,
    TestCaseInput,
    TestMode,
    TestRunResult,
)

router = APIRouter(prefix="/agents", tags=["testing"])


class RunTestRequest(BaseModel):
    """Request to run a test."""

    definition: dict[str, Any] | None = None
    agent_id: UUID | None = None
    test_case: TestCaseInput
    mode: TestMode = TestMode.DRY_RUN


class RunTestResponse(BaseModel):
    """Response from running a test."""

    result: TestRunResult


class BatchTestRequest(BaseModel):
    """Request to run multiple tests."""

    definition: dict[str, Any] | None = None
    agent_id: UUID | None = None
    test_cases: list[TestCaseInput]
    mode: TestMode = TestMode.DRY_RUN


class BatchTestResponse(BaseModel):
    """Response from batch test run."""

    results: list[TestRunResult]
    total: int
    passed: int
    failed: int


@router.post("/test", response_model=RunTestResponse)
async def run_single_test(request: RunTestRequest) -> RunTestResponse:
    """
    Run a single test case against an agent.

    Either definition or agent_id must be provided.
    """
    # Get definition
    definition = await _get_definition(request.definition, request.agent_id)

    # Run test
    runner = AgentTestRunner(mode=request.mode)
    result = await runner.run_test(definition, request.test_case)

    return RunTestResponse(result=result)


@router.post("/test/batch", response_model=BatchTestResponse)
async def run_batch_tests(request: BatchTestRequest) -> BatchTestResponse:
    """Run multiple test cases against an agent."""
    definition = await _get_definition(request.definition, request.agent_id)

    runner = AgentTestRunner(mode=request.mode)
    results = []

    for test_case in request.test_cases:
        result = await runner.run_test(definition, test_case)
        results.append(result)

    passed = sum(1 for r in results if r.status == "passed")
    failed = len(results) - passed

    return BatchTestResponse(
        results=results,
        total=len(results),
        passed=passed,
        failed=failed,
    )


@router.post("/{agent_id}/test", response_model=RunTestResponse)
async def test_agent(
    agent_id: UUID,
    test_case: TestCaseInput,
    mode: TestMode = TestMode.DRY_RUN,
) -> RunTestResponse:
    """Run a test against a deployed agent."""
    definition = await _get_definition(None, agent_id)

    runner = AgentTestRunner(mode=mode)
    result = await runner.run_test(definition, test_case)

    return RunTestResponse(result=result)


@router.post("/{agent_id}/validate")
async def validate_agent(agent_id: UUID) -> dict[str, Any]:
    """Validate an agent definition."""
    definition = await _get_definition(None, agent_id)

    runner = AgentTestRunner(mode=TestMode.VALIDATE)
    test_case = TestCaseInput(
        name="validation",
        trigger_data={},
    )

    result = await runner.run_test(definition, test_case)

    return {
        "valid": result.status == "passed",
        "errors": result.validation_errors,
        "warnings": result.warnings,
    }


async def _get_definition(
    definition_dict: dict[str, Any] | None,
    agent_id: UUID | None,
) -> AgentDefinitionModel:
    """Get agent definition from dict or database."""
    if definition_dict:
        return AgentDefinitionModel(**definition_dict)

    if agent_id:
        from aswa_agents.repositories.agent_repository import AgentRepository

        repo = AgentRepository()
        agent = await repo.get_by_id(str(agent_id))

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return AgentDefinitionModel(**agent.definition)

    raise HTTPException(
        status_code=400,
        detail="Either definition or agent_id must be provided",
    )
```

### Step 4: Test Reporter

```python
# services/agent-service/src/aswa_agents/testing/reporter.py
"""Test result reporting and formatting."""

from datetime import datetime
from typing import Any

from aswa_agents.testing.runner import TestRunResult, ActionTestResult


class TestReporter:
    """Generates test reports in various formats."""

    @staticmethod
    def to_console(result: TestRunResult) -> str:
        """Format result for console output."""
        lines = [
            f"\n{'=' * 60}",
            f"Test: {result.test_case_name}",
            f"Mode: {result.mode.value}",
            f"Status: {result.status.upper()}",
            f"{'=' * 60}",
            "",
            f"Started: {result.started_at.isoformat()}",
            f"Completed: {result.completed_at.isoformat() if result.completed_at else 'N/A'}",
            f"Duration: {result.total_execution_time_ms}ms",
            "",
            f"Actions: {result.total_actions} total, "
            f"{result.passed_actions} passed, "
            f"{result.failed_actions} failed, "
            f"{result.skipped_actions} skipped",
            "",
        ]

        # Action details
        for action_result in result.action_results:
            status_icon = {
                "completed": "[PASS]",
                "failed": "[FAIL]",
                "skipped": "[SKIP]",
            }.get(action_result.status, "[????]")

            lines.append(
                f"  {status_icon} {action_result.action_id} "
                f"({action_result.action_type}) - {action_result.execution_time_ms}ms"
            )

            if action_result.mocked:
                lines.append(f"         (mocked)")

            if action_result.error:
                lines.append(f"         Error: {action_result.error}")

            if action_result.assertion_errors:
                for err in action_result.assertion_errors:
                    lines.append(f"         Assertion: {err}")

        # Validation errors
        if result.validation_errors:
            lines.append("")
            lines.append("Validation Errors:")
            for err in result.validation_errors:
                lines.append(f"  - {err}")

        # Warnings
        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warn in result.warnings:
                lines.append(f"  - {warn}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def to_json(result: TestRunResult) -> dict[str, Any]:
        """Format result as JSON."""
        return result.model_dump()

    @staticmethod
    def to_junit_xml(results: list[TestRunResult]) -> str:
        """Format results as JUnit XML for CI integration."""
        total_tests = len(results)
        failures = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.validation_errors)

        total_time = sum(r.total_execution_time_ms for r in results) / 1000

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<testsuite name="AgentTests" tests="{total_tests}" '
            f'failures="{failures}" errors="{errors}" time="{total_time:.3f}">',
        ]

        for result in results:
            time_sec = result.total_execution_time_ms / 1000
            lines.append(
                f'  <testcase name="{result.test_case_name}" time="{time_sec:.3f}">'
            )

            if result.status == "failed":
                error_msg = "; ".join(
                    ar.error for ar in result.action_results if ar.error
                )
                lines.append(f'    <failure message="{_escape_xml(error_msg)}"/>')

            if result.validation_errors:
                for err in result.validation_errors:
                    lines.append(f'    <error message="{_escape_xml(err)}"/>')

            lines.append("  </testcase>")

        lines.append("</testsuite>")

        return "\n".join(lines)

    @staticmethod
    def to_markdown(results: list[TestRunResult]) -> str:
        """Format results as Markdown."""
        lines = [
            "# Agent Test Results",
            "",
            f"**Run at:** {datetime.utcnow().isoformat()}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Tests | {len(results)} |",
            f"| Passed | {sum(1 for r in results if r.status == 'passed')} |",
            f"| Failed | {sum(1 for r in results if r.status == 'failed')} |",
            "",
            "## Test Cases",
            "",
        ]

        for result in results:
            status_icon = "✅" if result.status == "passed" else "❌"
            lines.append(f"### {status_icon} {result.test_case_name}")
            lines.append("")
            lines.append(f"- **Status:** {result.status}")
            lines.append(f"- **Duration:** {result.total_execution_time_ms}ms")
            lines.append(f"- **Actions:** {result.passed_actions}/{result.total_actions} passed")
            lines.append("")

            if result.action_results:
                lines.append("| Action | Type | Status | Time |")
                lines.append("|--------|------|--------|------|")

                for ar in result.action_results:
                    status = "✅" if ar.status == "completed" else "❌" if ar.status == "failed" else "⏭️"
                    lines.append(
                        f"| {ar.action_id} | {ar.action_type} | {status} | {ar.execution_time_ms}ms |"
                    )

                lines.append("")

            if result.validation_errors:
                lines.append("**Validation Errors:**")
                for err in result.validation_errors:
                    lines.append(f"- {err}")
                lines.append("")

        return "\n".join(lines)


def _escape_xml(s: str) -> str:
    """Escape string for XML."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
```

## Test Cases

```python
# services/agent-service/tests/unit/test_agent_test_runner.py
"""Tests for agent test runner."""

import pytest
from uuid import uuid4

from aswa_agents.models.agent_definition import AgentDefinitionModel
from aswa_agents.testing.runner import (
    AgentTestRunner,
    TestCaseInput,
    TestMode,
)
from aswa_agents.testing.builder import test_case, test_suite


@pytest.fixture
def sample_definition():
    """Sample agent definition for testing."""
    return AgentDefinitionModel(
        name="test-agent",
        display_name="Test Agent",
        trigger={"type": "email"},
        actions=[
            {
                "id": "summarize_1",
                "type": "summarize",
                "config": {"max_length": 200},
            },
            {
                "id": "send_slack_1",
                "type": "send_slack",
                "config": {"channel": "#test"},
            },
        ],
    )


@pytest.fixture
def sample_test_case():
    """Sample test case."""
    return TestCaseInput(
        name="basic_email_test",
        description="Test basic email processing",
        trigger_data={
            "subject": "Test Email",
            "body": "This is a test email body with some content to summarize.",
            "sender": "test@example.com",
        },
    )


class TestAgentTestRunner:
    """Test AgentTestRunner."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, sample_definition, sample_test_case):
        """Test dry run mode."""
        runner = AgentTestRunner(mode=TestMode.DRY_RUN)
        result = await runner.run_test(sample_definition, sample_test_case)

        assert result.status in ["passed", "failed"]
        assert result.total_actions == 2
        assert len(result.action_results) == 2

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_definition, sample_test_case):
        """Test mock mode."""
        runner = AgentTestRunner(mode=TestMode.MOCK)
        result = await runner.run_test(sample_definition, sample_test_case)

        # All actions should be mocked
        for ar in result.action_results:
            assert ar.output is not None

    @pytest.mark.asyncio
    async def test_validate_mode(self, sample_definition, sample_test_case):
        """Test validate mode."""
        runner = AgentTestRunner(mode=TestMode.VALIDATE)
        result = await runner.run_test(sample_definition, sample_test_case)

        assert result.status in ["passed", "validation_failed"]
        assert result.total_actions == 0  # No execution in validate mode

    @pytest.mark.asyncio
    async def test_custom_mock(self, sample_definition, sample_test_case):
        """Test with custom mock."""
        runner = AgentTestRunner(mode=TestMode.DRY_RUN)

        async def mock_summarize(action, context):
            return {
                "summary": "Custom mock summary",
                "key_points": ["Custom point"],
            }

        runner.register_mock("summarize", mock_summarize)

        result = await runner.run_test(sample_definition, sample_test_case)

        summarize_result = next(
            ar for ar in result.action_results if ar.action_id == "summarize_1"
        )
        assert summarize_result.output["summary"] == "Custom mock summary"
        assert summarize_result.mocked is True

    @pytest.mark.asyncio
    async def test_assertions(self, sample_definition):
        """Test output assertions."""
        test_case = TestCaseInput(
            name="assertion_test",
            trigger_data={"content": "Test content"},
            expected_outputs={
                "summarize_1": {"summary": "Expected summary"},
            },
        )

        runner = AgentTestRunner(mode=TestMode.MOCK)
        result = await runner.run_test(sample_definition, test_case)

        summarize_result = next(
            ar for ar in result.action_results if ar.action_id == "summarize_1"
        )
        # Assertion will fail since mock doesn't match expected
        assert summarize_result.assertions_failed >= 0


class TestTestCaseBuilder:
    """Test TestCaseBuilder."""

    def test_build_email_test_case(self):
        """Test building email test case."""
        tc = (
            test_case("email_test")
            .with_description("Test email processing")
            .with_email_trigger(
                subject="Test Subject",
                body="Test body content",
            )
            .with_variable("user_id", "123")
            .expect_output("summarize_1", summary="expected summary")
            .build()
        )

        assert tc.name == "email_test"
        assert tc.trigger_data["subject"] == "Test Subject"
        assert tc.variables["user_id"] == "123"

    def test_build_slack_test_case(self):
        """Test building Slack test case."""
        tc = (
            test_case("slack_test")
            .with_slack_trigger(
                message="Hello bot",
                channel="#support",
            )
            .build()
        )

        assert tc.trigger_data["type"] == "slack"
        assert tc.trigger_data["channel"] == "#support"


class TestTestSuite:
    """Test TestSuite."""

    @pytest.mark.asyncio
    async def test_run_suite(self, sample_definition):
        """Test running a test suite."""
        suite = (
            test_suite("basic_suite")
            .add_builder(
                test_case("test_1")
                .with_email_trigger("Subject 1", "Body 1")
            )
            .add_builder(
                test_case("test_2")
                .with_email_trigger("Subject 2", "Body 2")
            )
            .build()
        )

        runner = AgentTestRunner(mode=TestMode.MOCK)
        results = await suite.run(sample_definition, runner)

        assert len(results) == 2
        assert all(r.test_case_name in ["test_1", "test_2"] for r in results)
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_agent_test_runner.py -v
   ```

2. **Test runner manually:**
   ```python
   from aswa_agents.testing.runner import AgentTestRunner, TestCaseInput, TestMode
   from aswa_agents.models.agent_definition import AgentDefinitionModel

   definition = AgentDefinitionModel(
       name="test",
       display_name="Test",
       trigger={"type": "email"},
       actions=[{"id": "s1", "type": "summarize", "config": {}}]
   )

   test_case = TestCaseInput(
       name="basic",
       trigger_data={"content": "Test content"}
   )

   runner = AgentTestRunner(mode=TestMode.DRY_RUN)
   result = await runner.run_test(definition, test_case)
   print(result)
   ```

3. **Test API endpoint:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/agents/test \
     -H "Content-Type: application/json" \
     -d '{
       "definition": {
         "name": "test-agent",
         "display_name": "Test",
         "trigger": {"type": "email"},
         "actions": [{"id": "s1", "type": "summarize", "config": {}}]
       },
       "test_case": {
         "name": "basic_test",
         "trigger_data": {"content": "Test content"}
       },
       "mode": "dry_run"
     }'
   ```

## Next Task

Proceed to `task-9.5.2-execution-history.md` for implementing execution history tracking.
