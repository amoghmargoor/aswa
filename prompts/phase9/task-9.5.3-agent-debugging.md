# Task 9.5.3: Agent Debugging

## Objective

Implement debugging tools for agents including step-through execution, breakpoints, variable inspection, and live debugging capabilities.

## Prerequisites

- Task 9.5.1-9.5.2 completed (Test Runner and Execution History)

## Implementation

### Step 1: Debug Session Manager

```python
# services/agent-service/src/aswa_agents/debugging/session.py
"""Debug session management for agents."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class DebugState(str, Enum):
    """Debug session state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STEP_INTO = "step_into"
    STEP_OVER = "step_over"
    COMPLETED = "completed"
    ERROR = "error"


class Breakpoint(BaseModel):
    """A breakpoint in the agent workflow."""

    id: UUID = Field(default_factory=uuid4)
    action_id: str
    condition: str | None = None  # Expression to evaluate
    enabled: bool = True
    hit_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DebugFrame(BaseModel):
    """A frame in the debug call stack."""

    action_id: str
    action_type: str
    index: int
    state: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DebugSnapshot(BaseModel):
    """Snapshot of debug state at a point in time."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    state: DebugState
    current_action: str | None = None
    action_index: int = 0
    call_stack: list[DebugFrame] = Field(default_factory=list)
    context_variables: dict[str, Any] = Field(default_factory=dict)
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    breakpoints_hit: list[str] = Field(default_factory=list)


class DebugSession:
    """
    Debug session for an agent execution.

    Provides breakpoints, stepping, and variable inspection.
    """

    def __init__(
        self,
        agent_id: UUID,
        tenant_id: str,
    ):
        self.id = uuid4()
        self.agent_id = agent_id
        self.tenant_id = tenant_id

        self.state = DebugState.IDLE
        self.breakpoints: dict[str, Breakpoint] = {}
        self.call_stack: list[DebugFrame] = []
        self.current_action_index = 0
        self.context_variables: dict[str, Any] = {}
        self.trigger_data: dict[str, Any] = {}
        self.outputs: dict[str, Any] = {}

        self._pause_event = asyncio.Event()
        self._resume_event = asyncio.Event()
        self._step_mode: DebugState | None = None
        self._step_target_index: int | None = None

        self._logger = logger.bind(
            component="DebugSession",
            session_id=str(self.id),
        )

    def add_breakpoint(
        self,
        action_id: str,
        condition: str | None = None,
    ) -> Breakpoint:
        """Add a breakpoint."""
        bp = Breakpoint(action_id=action_id, condition=condition)
        self.breakpoints[action_id] = bp

        self._logger.info(
            "Added breakpoint",
            action_id=action_id,
            condition=condition,
        )

        return bp

    def remove_breakpoint(self, action_id: str) -> bool:
        """Remove a breakpoint."""
        if action_id in self.breakpoints:
            del self.breakpoints[action_id]
            return True
        return False

    def toggle_breakpoint(self, action_id: str) -> bool:
        """Toggle breakpoint enabled state."""
        if action_id in self.breakpoints:
            self.breakpoints[action_id].enabled = not self.breakpoints[action_id].enabled
            return self.breakpoints[action_id].enabled
        return False

    async def check_breakpoint(
        self,
        action_id: str,
        context: dict[str, Any],
    ) -> bool:
        """
        Check if breakpoint should trigger.

        Returns True if execution should pause.
        """
        bp = self.breakpoints.get(action_id)

        if not bp or not bp.enabled:
            return False

        # Check condition if present
        if bp.condition:
            try:
                should_break = self._evaluate_condition(bp.condition, context)
                if not should_break:
                    return False
            except Exception as e:
                self._logger.warning(
                    "Breakpoint condition error",
                    action_id=action_id,
                    error=str(e),
                )

        bp.hit_count += 1

        self._logger.info(
            "Breakpoint hit",
            action_id=action_id,
            hit_count=bp.hit_count,
        )

        return True

    def _evaluate_condition(
        self,
        condition: str,
        context: dict[str, Any],
    ) -> bool:
        """Safely evaluate a breakpoint condition."""
        # Simple expression evaluation
        # In production, use a proper expression parser
        try:
            # Create safe evaluation context
            safe_context = {
                "trigger": context.get("trigger_data", {}),
                "outputs": context.get("outputs", {}),
                "vars": context.get("variables", {}),
            }

            # Only allow safe operations
            result = eval(condition, {"__builtins__": {}}, safe_context)
            return bool(result)
        except Exception:
            return True  # Default to breaking if condition fails

    async def pause(self) -> None:
        """Pause execution."""
        self.state = DebugState.PAUSED
        self._pause_event.clear()
        self._resume_event.clear()

        self._logger.info("Execution paused")

    async def resume(self) -> None:
        """Resume execution."""
        self.state = DebugState.RUNNING
        self._step_mode = None
        self._resume_event.set()

        self._logger.info("Execution resumed")

    async def step_into(self) -> None:
        """Step to next action."""
        self.state = DebugState.STEP_INTO
        self._step_mode = DebugState.STEP_INTO
        self._resume_event.set()

        self._logger.info("Step into")

    async def step_over(self) -> None:
        """Step over current action."""
        self.state = DebugState.STEP_OVER
        self._step_mode = DebugState.STEP_OVER
        self._step_target_index = self.current_action_index + 1
        self._resume_event.set()

        self._logger.info("Step over")

    async def wait_for_resume(self) -> DebugState:
        """Wait for resume signal."""
        await self._resume_event.wait()
        return self._step_mode or DebugState.RUNNING

    def push_frame(
        self,
        action_id: str,
        action_type: str,
        input_data: dict[str, Any],
    ) -> DebugFrame:
        """Push a new frame to the call stack."""
        frame = DebugFrame(
            action_id=action_id,
            action_type=action_type,
            index=self.current_action_index,
            state="executing",
            input_data=input_data,
            started_at=datetime.utcnow(),
        )

        self.call_stack.append(frame)
        return frame

    def pop_frame(
        self,
        output_data: dict[str, Any] | None = None,
        state: str = "completed",
    ) -> DebugFrame | None:
        """Pop the top frame from the call stack."""
        if not self.call_stack:
            return None

        frame = self.call_stack[-1]
        frame.output_data = output_data
        frame.state = state
        frame.completed_at = datetime.utcnow()

        return self.call_stack.pop()

    def get_snapshot(self) -> DebugSnapshot:
        """Get current debug state snapshot."""
        return DebugSnapshot(
            state=self.state,
            current_action=self.call_stack[-1].action_id if self.call_stack else None,
            action_index=self.current_action_index,
            call_stack=self.call_stack.copy(),
            context_variables=self.context_variables.copy(),
            trigger_data=self.trigger_data.copy(),
            outputs=self.outputs.copy(),
            breakpoints_hit=[
                bp.action_id for bp in self.breakpoints.values()
                if bp.hit_count > 0
            ],
        )

    def set_variable(self, name: str, value: Any) -> None:
        """Set a context variable for debugging."""
        self.context_variables[name] = value

    def get_variable(self, name: str) -> Any:
        """Get a context variable."""
        return self.context_variables.get(name)


class DebugSessionManager:
    """Manages active debug sessions."""

    _sessions: dict[UUID, DebugSession] = {}

    @classmethod
    def create_session(
        cls,
        agent_id: UUID,
        tenant_id: str,
    ) -> DebugSession:
        """Create a new debug session."""
        session = DebugSession(agent_id=agent_id, tenant_id=tenant_id)
        cls._sessions[session.id] = session
        return session

    @classmethod
    def get_session(cls, session_id: UUID) -> DebugSession | None:
        """Get a debug session by ID."""
        return cls._sessions.get(session_id)

    @classmethod
    def get_sessions_for_agent(cls, agent_id: UUID) -> list[DebugSession]:
        """Get all sessions for an agent."""
        return [s for s in cls._sessions.values() if s.agent_id == agent_id]

    @classmethod
    def end_session(cls, session_id: UUID) -> bool:
        """End and remove a debug session."""
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            return True
        return False

    @classmethod
    def clear_all(cls) -> None:
        """Clear all sessions (for testing)."""
        cls._sessions.clear()
```

### Step 2: Debug Executor

```python
# services/agent-service/src/aswa_agents/debugging/executor.py
"""Debug executor for step-through execution."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from aswa_agents.actions.base import ActionContext, ActionResult
from aswa_agents.actions.factory import ActionFactory, ActionPipeline
from aswa_agents.debugging.session import DebugSession, DebugState
from aswa_agents.models.agent_definition import AgentDefinitionModel

logger = structlog.get_logger()


class DebugExecutor:
    """
    Executes agent workflows in debug mode.

    Supports breakpoints, stepping, and variable inspection.
    """

    def __init__(self, session: DebugSession):
        self.session = session
        self._logger = logger.bind(
            component="DebugExecutor",
            session_id=str(session.id),
        )

    async def execute(
        self,
        definition: AgentDefinitionModel,
        trigger_data: dict[str, Any],
    ) -> dict[str, ActionResult]:
        """
        Execute agent in debug mode.

        Args:
            definition: Agent definition to execute
            trigger_data: Trigger data for the execution

        Returns:
            Dict mapping action IDs to results
        """
        # Build pipeline
        factory = ActionFactory()
        pipeline = factory.create_from_definition(definition.model_dump())

        # Initialize session state
        self.session.trigger_data = trigger_data
        self.session.state = DebugState.RUNNING

        # Create context
        context = ActionContext(
            execution_id=UUID(int=0),  # Placeholder
            agent_id=self.session.agent_id,
            tenant_id=self.session.tenant_id,
            trigger_data=trigger_data,
            variables=self.session.context_variables.copy(),
        )

        results: dict[str, ActionResult] = {}
        execution_order = pipeline.get_execution_order()

        for idx, action in enumerate(execution_order):
            self.session.current_action_index = idx

            # Check breakpoint
            should_pause = await self.session.check_breakpoint(
                action.action_id,
                {
                    "trigger_data": context.trigger_data,
                    "outputs": context.previous_outputs,
                    "variables": context.variables,
                },
            )

            if should_pause:
                await self.session.pause()

            # Wait if paused
            if self.session.state == DebugState.PAUSED:
                self._logger.info(
                    "Waiting at breakpoint",
                    action_id=action.action_id,
                )
                step_mode = await self.session.wait_for_resume()

                if step_mode == DebugState.STEP_INTO:
                    # Will pause after this action
                    pass

            # Push debug frame
            self.session.push_frame(
                action_id=action.action_id,
                action_type=action.action_type,
                input_data=dict(context.trigger_data),
            )

            # Execute action
            self._logger.info(
                "Executing action in debug mode",
                action_id=action.action_id,
                index=idx,
            )

            try:
                result = await action.run(context)
                results[action.action_id] = result

                # Update context
                if result.output:
                    context.previous_outputs[action.action_id] = result.output
                    self.session.outputs[action.action_id] = result.output

                # Pop frame with success
                self.session.pop_frame(
                    output_data=result.output,
                    state="completed" if result.is_success else "failed",
                )

            except Exception as e:
                self._logger.error(
                    "Action failed in debug mode",
                    action_id=action.action_id,
                    error=str(e),
                )

                result = ActionResult(
                    action_id=action.action_id,
                    status="failed",
                    error=str(e),
                )
                results[action.action_id] = result

                self.session.pop_frame(state="error")
                self.session.state = DebugState.ERROR
                break

            # Check for step mode
            if self.session._step_mode == DebugState.STEP_INTO:
                await self.session.pause()

        # Mark session complete
        if self.session.state != DebugState.ERROR:
            self.session.state = DebugState.COMPLETED

        return results

    async def execute_single_action(
        self,
        action_id: str,
        action_type: str,
        config: dict[str, Any],
        input_data: dict[str, Any],
    ) -> ActionResult:
        """
        Execute a single action for debugging.

        Useful for testing individual actions in isolation.
        """
        from aswa_agents.actions.registry import ActionRegistry

        action = ActionRegistry.create(action_type, action_id, config)

        context = ActionContext(
            execution_id=UUID(int=0),
            agent_id=self.session.agent_id,
            tenant_id=self.session.tenant_id,
            trigger_data=input_data,
            previous_outputs=self.session.outputs.copy(),
            variables=self.session.context_variables.copy(),
        )

        return await action.run(context)


class DebugInspector:
    """Inspects debug session state."""

    def __init__(self, session: DebugSession):
        self.session = session

    def get_current_context(self) -> dict[str, Any]:
        """Get current execution context."""
        return {
            "trigger_data": self.session.trigger_data,
            "outputs": self.session.outputs,
            "variables": self.session.context_variables,
        }

    def get_variable_at_path(self, path: str) -> Any:
        """
        Get variable value using dot notation path.

        Examples:
            "trigger.subject"
            "outputs.summarize_1.summary"
            "vars.custom_var"
        """
        parts = path.split(".")

        if parts[0] == "trigger":
            current = self.session.trigger_data
        elif parts[0] == "outputs":
            current = self.session.outputs
        elif parts[0] == "vars":
            current = self.session.context_variables
        else:
            return None

        for part in parts[1:]:
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

    def evaluate_expression(self, expression: str) -> Any:
        """
        Evaluate an expression in the current context.

        Supports basic operations on context variables.
        """
        context = {
            "trigger": self.session.trigger_data,
            "outputs": self.session.outputs,
            "vars": self.session.context_variables,
        }

        try:
            # Limited safe evaluation
            result = eval(expression, {"__builtins__": {}}, context)
            return result
        except Exception as e:
            return f"Error: {str(e)}"

    def get_call_stack_trace(self) -> list[dict[str, Any]]:
        """Get formatted call stack trace."""
        return [
            {
                "index": frame.index,
                "action_id": frame.action_id,
                "action_type": frame.action_type,
                "state": frame.state,
                "duration_ms": (
                    int((frame.completed_at - frame.started_at).total_seconds() * 1000)
                    if frame.completed_at and frame.started_at else None
                ),
            }
            for frame in self.session.call_stack
        ]
```

### Step 3: Debug API Endpoints

```python
# services/agent-service/src/aswa_agents/api/debugging.py
"""API endpoints for agent debugging."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from aswa_agents.debugging.session import (
    DebugSession,
    DebugSessionManager,
    DebugSnapshot,
    Breakpoint,
    DebugState,
)
from aswa_agents.debugging.executor import DebugExecutor, DebugInspector
from aswa_agents.models.agent_definition import AgentDefinitionModel

router = APIRouter(prefix="/debug", tags=["debugging"])


class CreateDebugSessionRequest(BaseModel):
    """Request to create debug session."""

    agent_id: UUID
    definition: dict[str, Any] | None = None


class CreateDebugSessionResponse(BaseModel):
    """Response with debug session info."""

    session_id: UUID
    agent_id: UUID
    state: DebugState


class AddBreakpointRequest(BaseModel):
    """Request to add breakpoint."""

    action_id: str
    condition: str | None = None


class BreakpointResponse(BaseModel):
    """Response with breakpoint info."""

    id: UUID
    action_id: str
    condition: str | None
    enabled: bool
    hit_count: int


class StartDebugRequest(BaseModel):
    """Request to start debug execution."""

    trigger_data: dict[str, Any]


class InspectRequest(BaseModel):
    """Request to inspect variable."""

    path: str | None = None
    expression: str | None = None


@router.post("/sessions", response_model=CreateDebugSessionResponse)
async def create_debug_session(request: CreateDebugSessionRequest) -> CreateDebugSessionResponse:
    """Create a new debug session."""
    tenant_id = "default-tenant"  # From auth in production

    session = DebugSessionManager.create_session(
        agent_id=request.agent_id,
        tenant_id=tenant_id,
    )

    return CreateDebugSessionResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        state=session.state,
    )


@router.get("/sessions/{session_id}")
async def get_debug_session(session_id: UUID) -> DebugSnapshot:
    """Get debug session state."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.get_snapshot()


@router.delete("/sessions/{session_id}")
async def end_debug_session(session_id: UUID) -> dict[str, Any]:
    """End a debug session."""
    success = DebugSessionManager.end_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session ended", "session_id": str(session_id)}


@router.post("/sessions/{session_id}/breakpoints", response_model=BreakpointResponse)
async def add_breakpoint(
    session_id: UUID,
    request: AddBreakpointRequest,
) -> BreakpointResponse:
    """Add a breakpoint to the session."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    bp = session.add_breakpoint(
        action_id=request.action_id,
        condition=request.condition,
    )

    return BreakpointResponse(
        id=bp.id,
        action_id=bp.action_id,
        condition=bp.condition,
        enabled=bp.enabled,
        hit_count=bp.hit_count,
    )


@router.delete("/sessions/{session_id}/breakpoints/{action_id}")
async def remove_breakpoint(session_id: UUID, action_id: str) -> dict[str, Any]:
    """Remove a breakpoint."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = session.remove_breakpoint(action_id)

    return {"removed": success}


@router.get("/sessions/{session_id}/breakpoints")
async def list_breakpoints(session_id: UUID) -> list[BreakpointResponse]:
    """List all breakpoints in session."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return [
        BreakpointResponse(
            id=bp.id,
            action_id=bp.action_id,
            condition=bp.condition,
            enabled=bp.enabled,
            hit_count=bp.hit_count,
        )
        for bp in session.breakpoints.values()
    ]


@router.post("/sessions/{session_id}/start")
async def start_debug_execution(
    session_id: UUID,
    request: StartDebugRequest,
) -> dict[str, Any]:
    """Start debug execution."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get agent definition
    from aswa_agents.repositories.agent_repository import AgentRepository

    repo = AgentRepository()
    agent = await repo.get_by_id(str(session.agent_id))

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    definition = AgentDefinitionModel(**agent.definition)

    # Start execution in background
    import asyncio

    executor = DebugExecutor(session)
    asyncio.create_task(executor.execute(definition, request.trigger_data))

    return {"message": "Debug execution started", "state": session.state.value}


@router.post("/sessions/{session_id}/resume")
async def resume_execution(session_id: UUID) -> dict[str, Any]:
    """Resume paused execution."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session.resume()

    return {"state": session.state.value}


@router.post("/sessions/{session_id}/step-into")
async def step_into(session_id: UUID) -> dict[str, Any]:
    """Step to next action."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session.step_into()

    return {"state": session.state.value}


@router.post("/sessions/{session_id}/step-over")
async def step_over(session_id: UUID) -> dict[str, Any]:
    """Step over current action."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session.step_over()

    return {"state": session.state.value}


@router.post("/sessions/{session_id}/pause")
async def pause_execution(session_id: UUID) -> dict[str, Any]:
    """Pause execution."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session.pause()

    return {"state": session.state.value}


@router.post("/sessions/{session_id}/inspect")
async def inspect_value(session_id: UUID, request: InspectRequest) -> dict[str, Any]:
    """Inspect a variable or evaluate expression."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    inspector = DebugInspector(session)

    if request.path:
        value = inspector.get_variable_at_path(request.path)
        return {"path": request.path, "value": value}
    elif request.expression:
        result = inspector.evaluate_expression(request.expression)
        return {"expression": request.expression, "result": result}
    else:
        return inspector.get_current_context()


@router.get("/sessions/{session_id}/stack")
async def get_call_stack(session_id: UUID) -> dict[str, Any]:
    """Get current call stack."""
    session = DebugSessionManager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    inspector = DebugInspector(session)

    return {
        "stack": inspector.get_call_stack_trace(),
        "current_index": session.current_action_index,
    }


@router.websocket("/sessions/{session_id}/ws")
async def debug_websocket(websocket: WebSocket, session_id: UUID):
    """WebSocket for real-time debug updates."""
    await websocket.accept()

    session = DebugSessionManager.get_session(session_id)

    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    try:
        last_state = None

        while True:
            # Send state updates
            if session.state != last_state:
                snapshot = session.get_snapshot()
                await websocket.send_json({
                    "type": "state_update",
                    "data": snapshot.model_dump(mode="json"),
                })
                last_state = session.state

            # Check for commands
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=0.5,
                )

                command = data.get("command")

                if command == "resume":
                    await session.resume()
                elif command == "step_into":
                    await session.step_into()
                elif command == "step_over":
                    await session.step_over()
                elif command == "pause":
                    await session.pause()
                elif command == "add_breakpoint":
                    session.add_breakpoint(
                        data.get("action_id"),
                        data.get("condition"),
                    )

                await websocket.send_json({
                    "type": "command_ack",
                    "command": command,
                })

            except asyncio.TimeoutError:
                pass

            # Check if session ended
            if session.state in [DebugState.COMPLETED, DebugState.ERROR]:
                await websocket.send_json({
                    "type": "session_ended",
                    "state": session.state.value,
                })
                break

    except WebSocketDisconnect:
        pass
```

## Test Cases

```python
# services/agent-service/tests/unit/test_debugging.py
"""Tests for agent debugging."""

import pytest
import asyncio
from uuid import uuid4

from aswa_agents.debugging.session import (
    DebugSession,
    DebugSessionManager,
    DebugState,
    Breakpoint,
)
from aswa_agents.debugging.executor import DebugExecutor, DebugInspector


class TestDebugSession:
    """Test DebugSession."""

    @pytest.fixture
    def session(self):
        return DebugSession(
            agent_id=uuid4(),
            tenant_id="test-tenant",
        )

    def test_add_breakpoint(self, session):
        """Test adding breakpoint."""
        bp = session.add_breakpoint("action_1", condition="trigger.priority > 5")

        assert bp.action_id == "action_1"
        assert bp.condition == "trigger.priority > 5"
        assert bp.enabled is True
        assert "action_1" in session.breakpoints

    def test_remove_breakpoint(self, session):
        """Test removing breakpoint."""
        session.add_breakpoint("action_1")

        result = session.remove_breakpoint("action_1")

        assert result is True
        assert "action_1" not in session.breakpoints

    def test_toggle_breakpoint(self, session):
        """Test toggling breakpoint."""
        session.add_breakpoint("action_1")

        result = session.toggle_breakpoint("action_1")
        assert result is False  # Was True, now False

        result = session.toggle_breakpoint("action_1")
        assert result is True  # Was False, now True

    @pytest.mark.asyncio
    async def test_check_breakpoint_no_condition(self, session):
        """Test checking breakpoint without condition."""
        session.add_breakpoint("action_1")

        result = await session.check_breakpoint("action_1", {})

        assert result is True
        assert session.breakpoints["action_1"].hit_count == 1

    @pytest.mark.asyncio
    async def test_check_breakpoint_with_condition(self, session):
        """Test checking breakpoint with condition."""
        session.add_breakpoint("action_1", condition="trigger['priority'] > 5")

        # Should not trigger
        result = await session.check_breakpoint(
            "action_1",
            {"trigger_data": {"priority": 3}},
        )
        assert result is False

        # Should trigger
        result = await session.check_breakpoint(
            "action_1",
            {"trigger_data": {"priority": 10}},
        )
        assert result is True

    def test_push_pop_frame(self, session):
        """Test call stack operations."""
        frame = session.push_frame(
            action_id="action_1",
            action_type="summarize",
            input_data={"content": "test"},
        )

        assert len(session.call_stack) == 1
        assert frame.action_id == "action_1"

        popped = session.pop_frame(output_data={"summary": "test"})

        assert len(session.call_stack) == 0
        assert popped.output_data == {"summary": "test"}

    def test_get_snapshot(self, session):
        """Test getting state snapshot."""
        session.trigger_data = {"subject": "Test"}
        session.add_breakpoint("action_1")

        snapshot = session.get_snapshot()

        assert snapshot.state == DebugState.IDLE
        assert snapshot.trigger_data == {"subject": "Test"}

    @pytest.mark.asyncio
    async def test_pause_resume(self, session):
        """Test pause and resume."""
        await session.pause()
        assert session.state == DebugState.PAUSED

        # Resume in background
        async def resume_later():
            await asyncio.sleep(0.1)
            await session.resume()

        asyncio.create_task(resume_later())

        state = await session.wait_for_resume()
        assert session.state == DebugState.RUNNING


class TestDebugSessionManager:
    """Test DebugSessionManager."""

    def setup_method(self):
        DebugSessionManager.clear_all()

    def test_create_session(self):
        """Test creating session."""
        session = DebugSessionManager.create_session(
            agent_id=uuid4(),
            tenant_id="test",
        )

        assert session is not None
        assert DebugSessionManager.get_session(session.id) == session

    def test_get_sessions_for_agent(self):
        """Test getting sessions for agent."""
        agent_id = uuid4()

        DebugSessionManager.create_session(agent_id, "test")
        DebugSessionManager.create_session(agent_id, "test")
        DebugSessionManager.create_session(uuid4(), "test")  # Different agent

        sessions = DebugSessionManager.get_sessions_for_agent(agent_id)

        assert len(sessions) == 2

    def test_end_session(self):
        """Test ending session."""
        session = DebugSessionManager.create_session(uuid4(), "test")

        result = DebugSessionManager.end_session(session.id)

        assert result is True
        assert DebugSessionManager.get_session(session.id) is None


class TestDebugInspector:
    """Test DebugInspector."""

    @pytest.fixture
    def session(self):
        session = DebugSession(uuid4(), "test")
        session.trigger_data = {
            "subject": "Test Subject",
            "priority": 5,
            "tags": ["urgent", "bug"],
        }
        session.outputs = {
            "summarize_1": {
                "summary": "Test summary",
                "key_points": ["Point 1", "Point 2"],
            }
        }
        session.context_variables = {
            "custom_var": "custom_value",
        }
        return session

    def test_get_variable_at_path(self, session):
        """Test getting variable at path."""
        inspector = DebugInspector(session)

        assert inspector.get_variable_at_path("trigger.subject") == "Test Subject"
        assert inspector.get_variable_at_path("trigger.tags.0") == "urgent"
        assert inspector.get_variable_at_path("outputs.summarize_1.summary") == "Test summary"
        assert inspector.get_variable_at_path("vars.custom_var") == "custom_value"
        assert inspector.get_variable_at_path("trigger.nonexistent") is None

    def test_evaluate_expression(self, session):
        """Test evaluating expression."""
        inspector = DebugInspector(session)

        result = inspector.evaluate_expression("trigger['priority'] * 2")
        assert result == 10

        result = inspector.evaluate_expression("len(trigger['tags'])")
        assert result == 2

    def test_get_current_context(self, session):
        """Test getting current context."""
        inspector = DebugInspector(session)

        context = inspector.get_current_context()

        assert "trigger_data" in context
        assert "outputs" in context
        assert "variables" in context
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_debugging.py -v
   ```

2. **Test debug session:**
   ```python
   from aswa_agents.debugging.session import DebugSessionManager
   from uuid import uuid4

   session = DebugSessionManager.create_session(uuid4(), "test")
   session.add_breakpoint("action_1")
   session.trigger_data = {"content": "test"}

   snapshot = session.get_snapshot()
   print(snapshot)
   ```

3. **Test API endpoints:**
   ```bash
   # Create session
   curl -X POST http://localhost:8000/api/v1/debug/sessions \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "..."}'

   # Add breakpoint
   curl -X POST http://localhost:8000/api/v1/debug/sessions/{id}/breakpoints \
     -H "Content-Type: application/json" \
     -d '{"action_id": "action_1"}'

   # Get state
   curl http://localhost:8000/api/v1/debug/sessions/{id}
   ```

## Next Task

Proceed to `task-9.6.1-approval-service.md` for implementing the approval service.
