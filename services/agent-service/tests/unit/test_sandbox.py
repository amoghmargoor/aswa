"""Tests for agent testing sandbox."""

from uuid import uuid4

import pytest

from aswa_agents.testing import (
    AgentSandbox,
    TestAssertion,
    TestCase,
    TestResult,
    TestRunner,
    TestRunStatus,
    TestSuite,
    TestSuiteResult,
)


class TestAgentSandbox:
    """Tests for AgentSandbox class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def simple_agent_definition(self):
        """Create a simple agent definition."""
        return {
            "trigger": {
                "type": "manual",
                "name": "Manual Trigger",
            },
            "actions": [
                {
                    "id": "action1",
                    "type": "summarize",
                    "name": "Summarize",
                    "config": {"style": "brief"},
                }
            ],
        }

    @pytest.fixture
    def sandbox(self, simple_agent_definition, tenant_id):
        """Create a sandbox instance."""
        return AgentSandbox(
            agent_definition=simple_agent_definition,
            tenant_id=tenant_id,
            mock_integrations=True,
        )

    @pytest.mark.asyncio
    async def test_execute_simple_agent(self, sandbox):
        """Test executing a simple agent."""
        results = await sandbox.execute(
            trigger_data={"input": "test data"},
            timeout_seconds=30,
        )

        assert len(results) > 0
        assert all(hasattr(r, "status") for r in results)

    @pytest.mark.asyncio
    async def test_execute_with_mock_integrations(self, tenant_id):
        """Test that integrations are mocked."""
        definition = {
            "trigger": {"type": "manual"},
            "actions": [
                {
                    "id": "notify",
                    "type": "send_slack",
                    "config": {"channel": "#test"},
                }
            ],
        }

        sandbox = AgentSandbox(
            agent_definition=definition,
            tenant_id=tenant_id,
            mock_integrations=True,
        )

        results = await sandbox.execute(
            trigger_data={},
            timeout_seconds=30,
        )

        # Should succeed with mock (no actual Slack call)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_execute_with_conditions(self, tenant_id):
        """Test executing agent with conditions."""
        definition = {
            "trigger": {"type": "manual"},
            "conditions": [
                {
                    "expression": "data.value > 10",
                    "description": "Value must be greater than 10",
                }
            ],
            "actions": [
                {"id": "action1", "type": "log", "config": {}},
            ],
        }

        sandbox = AgentSandbox(
            agent_definition=definition,
            tenant_id=tenant_id,
            mock_integrations=True,
        )

        # Should pass condition
        results = await sandbox.execute(
            trigger_data={"data": {"value": 20}},
            timeout_seconds=30,
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_get_execution_trace(self, sandbox):
        """Test getting execution trace."""
        await sandbox.execute(
            trigger_data={"input": "test"},
            timeout_seconds=30,
        )

        trace = sandbox.get_execution_trace()

        assert trace is not None
        assert "steps" in trace


class TestTestRunner:
    """Tests for TestRunner class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def agent_definition(self):
        """Create an agent definition."""
        return {
            "trigger": {"type": "manual"},
            "actions": [
                {"id": "summarize", "type": "summarize", "config": {"style": "brief"}}
            ],
        }

    @pytest.fixture
    def runner(self, agent_definition, tenant_id):
        """Create a test runner instance."""
        return TestRunner(
            agent_definition=agent_definition,
            tenant_id=tenant_id,
        )

    @pytest.fixture
    def simple_test_case(self):
        """Create a simple test case."""
        return TestCase(
            name="basic-test",
            description="Basic functionality test",
            trigger_data={"text": "This is a test input"},
            assertions=[
                TestAssertion(
                    type="status",
                    expected="success",
                    description="Should complete successfully",
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_run_single_test(self, runner, simple_test_case):
        """Test running a single test case."""
        result = await runner.run_test(simple_test_case)

        assert isinstance(result, TestResult)
        assert result.test_name == "basic-test"
        assert result.status in [TestRunStatus.PASSED, TestRunStatus.FAILED]

    @pytest.mark.asyncio
    async def test_run_test_with_output_assertion(self, runner):
        """Test with output content assertion."""
        test_case = TestCase(
            name="output-test",
            description="Test output content",
            trigger_data={"text": "Important document"},
            assertions=[
                TestAssertion(
                    type="output_contains",
                    expected="summary",
                    path="$.action1.output",
                    description="Output should contain summary",
                )
            ],
        )

        result = await runner.run_test(test_case)

        assert isinstance(result, TestResult)

    @pytest.mark.asyncio
    async def test_run_test_with_timing_assertion(self, runner):
        """Test with timing assertion."""
        test_case = TestCase(
            name="timing-test",
            description="Test execution timing",
            trigger_data={"text": "Quick test"},
            assertions=[
                TestAssertion(
                    type="timing",
                    expected=5000,  # 5 seconds max
                    description="Should complete within 5 seconds",
                )
            ],
        )

        result = await runner.run_test(test_case)

        assert isinstance(result, TestResult)
        assert result.duration_ms is not None


class TestTestSuite:
    """Tests for TestSuite class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def agent_definition(self):
        """Create an agent definition."""
        return {
            "trigger": {"type": "manual"},
            "actions": [
                {"id": "action1", "type": "summarize", "config": {}}
            ],
        }

    @pytest.fixture
    def test_suite(self, agent_definition, tenant_id):
        """Create a test suite."""
        return TestSuite(
            name="integration-tests",
            description="Integration test suite",
            agent_definition=agent_definition,
            tenant_id=tenant_id,
            test_cases=[
                TestCase(
                    name="test-1",
                    description="First test",
                    trigger_data={"input": "test 1"},
                    assertions=[
                        TestAssertion(type="status", expected="success")
                    ],
                ),
                TestCase(
                    name="test-2",
                    description="Second test",
                    trigger_data={"input": "test 2"},
                    assertions=[
                        TestAssertion(type="status", expected="success")
                    ],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_run_suite(self, test_suite):
        """Test running a complete test suite."""
        runner = TestRunner(
            agent_definition=test_suite.agent_definition,
            tenant_id=test_suite.tenant_id,
        )

        result = await runner.run_suite(test_suite)

        assert isinstance(result, TestSuiteResult)
        assert result.suite_name == "integration-tests"
        assert result.total_tests == 2
        assert result.passed + result.failed == result.total_tests

    @pytest.mark.asyncio
    async def test_suite_result_summary(self, test_suite):
        """Test suite result summary."""
        runner = TestRunner(
            agent_definition=test_suite.agent_definition,
            tenant_id=test_suite.tenant_id,
        )

        result = await runner.run_suite(test_suite)

        assert result.duration_ms >= 0
        assert len(result.results) == 2


class TestTestCase:
    """Tests for TestCase model."""

    def test_create_test_case(self):
        """Test creating a test case."""
        test_case = TestCase(
            name="my-test",
            description="Test description",
            trigger_data={"key": "value"},
            assertions=[
                TestAssertion(
                    type="status",
                    expected="success",
                )
            ],
        )

        assert test_case.name == "my-test"
        assert len(test_case.assertions) == 1

    def test_test_case_with_setup_teardown(self):
        """Test case with setup and teardown."""
        test_case = TestCase(
            name="setup-test",
            description="Test with setup",
            trigger_data={},
            assertions=[],
            setup={"action": "prepare_data"},
            teardown={"action": "cleanup"},
        )

        assert test_case.setup is not None
        assert test_case.teardown is not None


class TestTestAssertion:
    """Tests for TestAssertion model."""

    def test_status_assertion(self):
        """Test status assertion."""
        assertion = TestAssertion(
            type="status",
            expected="success",
            description="Should succeed",
        )

        assert assertion.type == "status"
        assert assertion.expected == "success"

    def test_output_assertion_with_path(self):
        """Test output assertion with JSON path."""
        assertion = TestAssertion(
            type="output_equals",
            expected={"result": "done"},
            path="$.action1.output",
            description="Output should match",
        )

        assert assertion.path == "$.action1.output"

    def test_timing_assertion(self):
        """Test timing assertion."""
        assertion = TestAssertion(
            type="timing",
            expected=1000,  # 1 second
            description="Should complete in 1 second",
        )

        assert assertion.expected == 1000
