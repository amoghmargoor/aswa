"""Agent testing framework - sandbox execution."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

from aswa_agents.actions.blocks import ActionContext, ActionRegistry, ActionResult, ActionStatus

logger = structlog.get_logger()


class TestRunStatus(str, Enum):
    """Status of a test run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class TestCase(BaseModel):
    """A test case for an agent."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, Any] = Field(default_factory=dict)
    expected_actions: list[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    assertions: list["TestAssertion"] = Field(default_factory=list)
    setup: dict[str, Any] | None = None
    teardown: dict[str, Any] | None = None


class TestAssertion(BaseModel):
    """An assertion to verify in a test."""

    type: str  # "output_equals", "output_contains", "action_called", "status", "timing"
    expected: Any = None
    target: str | None = None  # action_id or output key
    path: str | None = None  # JSON path for output assertions
    description: str = ""
    message: str = ""


class TestResult(BaseModel):
    """Result of a test case execution."""

    test_case_id: UUID
    test_case_name: str
    status: TestRunStatus
    duration_ms: float = 0
    action_results: list[ActionResult] = Field(default_factory=list)
    assertion_results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @property
    def test_name(self) -> str:
        """Alias for test_case_name."""
        return self.test_case_name


class TestSuite(BaseModel):
    """A collection of test cases."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    agent_id: UUID | None = None
    agent_definition: dict[str, Any] | None = None
    tenant_id: UUID | None = None
    test_cases: list[TestCase] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestSuiteResult(BaseModel):
    """Result of running a test suite."""

    suite_id: UUID
    suite_name: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    duration_ms: float = 0
    test_results: list[TestResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @property
    def results(self) -> list[TestResult]:
        """Alias for test_results."""
        return self.test_results


class AgentSandbox:
    """Sandbox for testing agent execution."""

    def __init__(
        self,
        agent_definition: dict[str, Any],
        tenant_id: UUID,
        mock_integrations: bool = True,
    ):
        self.agent_definition = agent_definition
        self.tenant_id = tenant_id
        self.mock_integrations = mock_integrations
        self.run_id = uuid4()
        self._logger = logger.bind(
            component="AgentSandbox",
            run_id=str(self.run_id),
        )
        self._execution_trace: dict[str, Any] = {"steps": [], "started_at": None, "completed_at": None}

    def get_execution_trace(self) -> dict[str, Any]:
        """Get the execution trace from the last run."""
        return self._execution_trace

    async def execute(
        self,
        trigger_data: dict[str, Any],
        timeout_seconds: int = 30,
    ) -> list[ActionResult]:
        """Execute agent in sandbox with given trigger data."""
        import time

        start_time = time.time()
        results: list[ActionResult] = []
        self._execution_trace = {
            "steps": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        try:
            # Build context
            context = ActionContext(
                agent_id=uuid4(),
                run_id=self.run_id,
                tenant_id=self.tenant_id,
                trigger_data=trigger_data,
                variables={},
                previous_outputs={},
                secrets=self._get_mock_secrets() if self.mock_integrations else {},
            )

            # Execute each action in order
            actions = self.agent_definition.get("actions", [])
            for action_def in actions:
                action_type = action_def.get("type")
                action_id = action_def.get("id", str(uuid4()))
                action_config = action_def.get("config", {})

                # Create action instance
                try:
                    action = ActionRegistry.create(action_type, action_id, action_config)
                except ValueError as e:
                    results.append(ActionResult(
                        action_id=action_id,
                        status=ActionStatus.FAILED,
                        error=str(e),
                    ))
                    continue

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    results.append(ActionResult(
                        action_id=action_id,
                        status=ActionStatus.FAILED,
                        error="Execution timeout",
                    ))
                    break

                # Execute action
                result = await asyncio.wait_for(
                    action.execute(context),
                    timeout=timeout_seconds - elapsed,
                )
                results.append(result)

                # Update context with output
                if result.status == ActionStatus.SUCCESS and result.output:
                    context.previous_outputs[action_id] = result.output

                # Stop on failure if configured
                if result.status == ActionStatus.FAILED:
                    self._logger.warning(
                        "Action failed, stopping execution",
                        action_id=action_id,
                        error=result.error,
                    )
                    break

            self._logger.info(
                "Sandbox execution complete",
                action_count=len(results),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except asyncio.TimeoutError:
            self._logger.error("Sandbox execution timed out")
            results.append(ActionResult(
                action_id="timeout",
                status=ActionStatus.FAILED,
                error=f"Execution timed out after {timeout_seconds}s",
            ))

        except Exception as e:
            self._logger.exception("Sandbox execution failed")
            results.append(ActionResult(
                action_id="error",
                status=ActionStatus.FAILED,
                error=str(e),
            ))

        return results

    def _get_mock_secrets(self) -> dict[str, str]:
        """Get mock secrets for sandbox execution."""
        return {
            "SLACK_BOT_TOKEN": "xoxb-mock-token",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/mock",
            "EMAIL_API_KEY": "mock-email-key",
            "JIRA_API_TOKEN": "mock-jira-token",
        }


class TestRunner:
    """Runs test suites against agents."""

    def __init__(
        self,
        tenant_id: UUID,
        agent_definition: dict[str, Any] | None = None,
    ):
        self.tenant_id = tenant_id
        self.agent_definition = agent_definition
        self._logger = logger.bind(component="TestRunner")

    async def run_suite(
        self,
        suite: TestSuite,
        agent_definition: dict[str, Any] | None = None,
    ) -> TestSuiteResult:
        """Run all tests in a suite."""
        import time

        # Use provided agent_definition or fall back to suite's or instance's
        definition = agent_definition or suite.agent_definition or self.agent_definition
        if not definition:
            raise ValueError("No agent definition provided")

        start_time = time.time()
        results: list[TestResult] = []

        self._logger.info(
            "Running test suite",
            suite_name=suite.name,
            test_count=len(suite.test_cases),
        )

        for test_case in suite.test_cases:
            result = await self.run_test(test_case, definition)
            results.append(result)

        # Calculate summary
        passed = sum(1 for r in results if r.status == TestRunStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestRunStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestRunStatus.ERROR)

        suite_result = TestSuiteResult(
            suite_id=suite.id,
            suite_name=suite.name,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            errors=errors,
            duration_ms=(time.time() - start_time) * 1000,
            test_results=results,
            completed_at=datetime.now(timezone.utc),
        )

        self._logger.info(
            "Test suite complete",
            suite_name=suite.name,
            passed=passed,
            failed=failed,
            errors=errors,
        )

        return suite_result

    async def run_test(
        self,
        test_case: TestCase,
        agent_definition: dict[str, Any] | None = None,
    ) -> TestResult:
        """Run a single test case."""
        import time

        # Use provided agent_definition or fall back to instance's
        definition = agent_definition or self.agent_definition
        if not definition:
            raise ValueError("No agent definition provided")

        start_time = time.time()
        result = TestResult(
            test_case_id=test_case.id,
            test_case_name=test_case.name,
            status=TestRunStatus.RUNNING,
        )

        try:
            # Create sandbox and execute
            sandbox = AgentSandbox(
                agent_definition=definition,
                tenant_id=self.tenant_id,
                mock_integrations=True,
            )

            action_results = await sandbox.execute(
                trigger_data=test_case.trigger_data,
                timeout_seconds=test_case.timeout_seconds,
            )

            result.action_results = action_results

            # Run assertions
            assertion_results = self._run_assertions(
                test_case.assertions,
                action_results,
                test_case.expected_outputs,
            )
            result.assertion_results = assertion_results

            # Determine overall status
            all_passed = all(a.get("passed", False) for a in assertion_results)
            no_failures = not any(
                r.status == ActionStatus.FAILED for r in action_results
                if r.action_id not in ("timeout", "error")
            )

            if all_passed and no_failures:
                result.status = TestRunStatus.PASSED
            else:
                result.status = TestRunStatus.FAILED

        except asyncio.TimeoutError:
            result.status = TestRunStatus.TIMEOUT
            result.error = "Test execution timed out"

        except Exception as e:
            result.status = TestRunStatus.ERROR
            result.error = str(e)
            self._logger.exception("Test execution error", test_name=test_case.name)

        result.duration_ms = (time.time() - start_time) * 1000
        result.completed_at = datetime.now(timezone.utc)

        return result

    def _run_assertions(
        self,
        assertions: list[TestAssertion],
        action_results: list[ActionResult],
        expected_outputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run assertions against results."""
        results = []

        # Build outputs map
        outputs = {}
        for result in action_results:
            if result.output:
                outputs[result.action_id] = result.output

        for assertion in assertions:
            assertion_result = {
                "type": assertion.type,
                "target": assertion.target,
                "expected": assertion.expected,
                "passed": False,
                "actual": None,
                "message": assertion.message,
            }

            try:
                if assertion.type == "output_equals":
                    actual = self._get_nested_value(outputs, assertion.target)
                    assertion_result["actual"] = actual
                    assertion_result["passed"] = actual == assertion.expected

                elif assertion.type == "output_contains":
                    actual = self._get_nested_value(outputs, assertion.target)
                    assertion_result["actual"] = actual
                    if isinstance(actual, str) and isinstance(assertion.expected, str):
                        assertion_result["passed"] = assertion.expected in actual
                    elif isinstance(actual, list):
                        assertion_result["passed"] = assertion.expected in actual

                elif assertion.type == "action_called":
                    called = any(r.action_id == assertion.target for r in action_results)
                    assertion_result["actual"] = called
                    assertion_result["passed"] = called == assertion.expected

                elif assertion.type == "action_status":
                    matching = [r for r in action_results if r.action_id == assertion.target]
                    if matching:
                        assertion_result["actual"] = matching[0].status.value
                        assertion_result["passed"] = matching[0].status.value == assertion.expected

            except Exception as e:
                assertion_result["error"] = str(e)

            results.append(assertion_result)

        # Check expected outputs
        for key, expected in expected_outputs.items():
            actual = self._get_nested_value(outputs, key)
            results.append({
                "type": "expected_output",
                "target": key,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            })

        return results

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
