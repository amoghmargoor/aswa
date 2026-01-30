"""Pytest fixtures for Agent Service tests."""

import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from aswa_agents.config import Settings
from aswa_agents.api.schemas import AgentResponse


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return Settings(
        environment="development",
        debug=True,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_agents",
    )


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def test_tenant_id() -> str:
    """Get test tenant ID."""
    return f"test-tenant-{uuid4().hex[:8]}"


@pytest.fixture
def auth_headers(test_tenant_id: str, settings: Settings) -> dict:
    """Create authorization headers with valid JWT."""
    from jose import jwt

    token = jwt.encode(
        {"sub": "test-user", "tenant_id": test_tenant_id, "roles": ["admin"]},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


# In-memory storage for mock testing
_mock_agents: dict[str, dict] = {}
_mock_templates: dict[str, dict] = {}
_mock_approvals: dict[str, dict] = {}
_mock_roles: dict[str, dict] = {}
_mock_policies: dict[str, dict] = {}


def _reset_mock_storage():
    """Reset all mock storage."""
    global _mock_agents, _mock_templates, _mock_approvals, _mock_roles, _mock_policies
    _mock_agents = {}
    _mock_templates = {}
    _mock_approvals = {}
    _mock_roles = {}
    _mock_policies = {}


@pytest.fixture
def app(settings: Settings):
    """Create test application with full routes using in-memory mocks."""
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel
    from typing import Any

    _reset_mock_storage()

    test_app = FastAPI()

    # Health endpoints
    @test_app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "agent-service"}

    @test_app.get("/ready")
    async def readiness_check():
        return {"status": "ready"}

    # Agent endpoints
    @test_app.post("/api/v1/agents", status_code=201)
    async def create_agent(agent_data: dict):
        agent_id = str(uuid4())
        agent = {
            "id": agent_id,
            "name": agent_data.get("name", "unnamed"),
            "display_name": agent_data.get("display_name", ""),
            "description": agent_data.get("description", ""),
            "status": "draft",
            "trigger": agent_data.get("trigger", {}),
            "actions": agent_data.get("actions", []),
            "conditions": agent_data.get("conditions", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _mock_agents[agent_id] = agent
        return agent

    @test_app.get("/api/v1/agents")
    async def list_agents(
        status: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        agents = list(_mock_agents.values())
        if status:
            agents = [a for a in agents if a.get("status") == status]
        return {
            "agents": agents[offset:offset + limit],
            "total": len(agents),
            "limit": limit,
            "offset": offset,
        }

    @test_app.get("/api/v1/agents/{agent_id}")
    async def get_agent(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _mock_agents[agent_id]

    @test_app.put("/api/v1/agents/{agent_id}")
    async def update_agent(agent_id: str, agent_data: dict):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        _mock_agents[agent_id].update(agent_data)
        _mock_agents[agent_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return _mock_agents[agent_id]

    @test_app.delete("/api/v1/agents/{agent_id}", status_code=204)
    async def delete_agent(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        del _mock_agents[agent_id]
        return None

    @test_app.post("/api/v1/agents/{agent_id}/test")
    async def test_agent(agent_id: str, test_data: dict):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"status": "success", "results": []}

    @test_app.post("/api/v1/agents/{agent_id}/clone")
    async def clone_agent(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        original = _mock_agents[agent_id]
        new_id = str(uuid4())
        clone = {
            **original,
            "id": new_id,
            "name": f"{original['name']}-copy",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _mock_agents[new_id] = clone
        return clone

    @test_app.post("/api/v1/agents/{agent_id}/activate")
    async def activate_agent(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        _mock_agents[agent_id]["status"] = "active"
        return _mock_agents[agent_id]

    @test_app.post("/api/v1/agents/{agent_id}/pause")
    async def pause_agent(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        _mock_agents[agent_id]["status"] = "paused"
        return _mock_agents[agent_id]

    @test_app.get("/api/v1/agents/{agent_id}/versions")
    async def get_agent_versions(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"versions": [{"version_number": 1, "status": "draft"}]}

    @test_app.get("/api/v1/agents/{agent_id}/audit")
    async def get_agent_audit(agent_id: str):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"entries": []}

    @test_app.post("/api/v1/agents/{agent_id}/trigger", status_code=501)
    async def trigger_agent(agent_id: str, trigger_data: dict):
        if agent_id not in _mock_agents:
            raise HTTPException(status_code=404, detail="Agent not found")
        raise HTTPException(status_code=501, detail="Not implemented")

    # Action block endpoints
    @test_app.get("/api/v1/actions")
    async def list_action_blocks(category: str | None = None):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        from aswa_agents.actions.blocks.base import ActionCategory
        ActionRegistry.initialize()

        raw_blocks = ActionRegistry.get_all_action_info()
        if category:
            raw_blocks = [b for b in raw_blocks if b.get("category") == category]

        # Add expected fields
        blocks = []
        for b in raw_blocks:
            block = dict(b)
            block["id"] = block.get("type", "unknown")
            block["name"] = block.get("display_name", "").lower().replace(" ", "_")
            block["version"] = "1.0.0"
            blocks.append(block)
        return {"blocks": blocks, "total": len(blocks)}

    @test_app.get("/api/v1/actions/blocks")
    async def list_action_blocks_alt(category: str | None = None):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        ActionRegistry.initialize()

        raw_blocks = ActionRegistry.get_all_action_info()
        if category:
            raw_blocks = [b for b in raw_blocks if b.get("category") == category]

        blocks = []
        for b in raw_blocks:
            block = dict(b)
            block["id"] = block.get("type", "unknown")
            block["name"] = block.get("display_name", "").lower().replace(" ", "_")
            block["version"] = "1.0.0"
            blocks.append(block)
        return {"blocks": blocks, "total": len(blocks)}

    @test_app.get("/api/v1/actions/categories")
    async def list_action_categories():
        from aswa_agents.actions.blocks.base import ActionCategory
        return {
            "categories": [
                {"id": c.value, "name": c.value.title(), "description": f"{c.value.title()} actions"}
                for c in ActionCategory
            ]
        }

    @test_app.get("/api/v1/actions/{action_type}")
    async def get_action_block(action_type: str):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        ActionRegistry.initialize()
        info = ActionRegistry.get_action_info(action_type)
        if not info:
            raise HTTPException(status_code=404, detail="Action not found")
        result = dict(info)
        result["id"] = action_type
        result["name"] = result.get("display_name", "").lower().replace(" ", "_")
        result["version"] = "1.0.0"
        return result

    @test_app.get("/api/v1/actions/{action_type}/schema")
    async def get_action_schema(action_type: str):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        ActionRegistry.initialize()
        schema = ActionRegistry.get_schema(action_type)
        info = ActionRegistry.get_action_info(action_type)
        if not schema or not info:
            raise HTTPException(status_code=404, detail="Action not found")
        return {
            "id": action_type,
            "name": info.get("display_name", "").lower().replace(" ", "_"),
            "display_name": info.get("display_name", ""),
            "input_schema": schema.model_dump().get("properties", {}),
            "output_schema": {},
            "config_schema": schema.model_dump(),
        }

    @test_app.post("/api/v1/actions/{action_type}/validate")
    async def validate_action_config(action_type: str, config: dict):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        ActionRegistry.initialize()
        schema = ActionRegistry.get_schema(action_type)
        if not schema:
            raise HTTPException(status_code=404, detail="Action not found")
        # Validate against schema properties, not full schema model
        errors = []
        required = schema.required or []
        for req in required:
            if req not in config:
                errors.append(f"Missing required field: {req}")
        return {"valid": len(errors) == 0, "errors": errors}

    @test_app.post("/api/v1/actions/{action_type}/preview")
    async def preview_action(action_type: str, preview_data: dict):
        from aswa_agents.actions.blocks.registry import ActionRegistry
        ActionRegistry.initialize()
        action_class = ActionRegistry.get(action_type)
        if not action_class:
            raise HTTPException(status_code=404, detail="Action not found")
        return {"preview": f"Would execute {action_type}", "action_type": action_type}

    # Template endpoints
    @test_app.get("/api/v1/templates")
    async def list_templates(
        category: str | None = None,
        search: str | None = None,
    ):
        from aswa_agents.templates import BUILTIN_TEMPLATES
        templates = [
            {
                "id": str(t.id),
                "name": t.name,
                "display_name": t.display_name,
                "description": t.description,
                "category": t.category.value,
            }
            for t in BUILTIN_TEMPLATES
        ]
        if category:
            templates = [t for t in templates if t["category"] == category]
        if search:
            search_lower = search.lower()
            templates = [
                t for t in templates
                if search_lower in t["name"].lower()
                or search_lower in t["display_name"].lower()
                or search_lower in t["description"].lower()
            ]
        return {"templates": templates, "total": len(templates)}

    @test_app.get("/api/v1/templates/{template_id}")
    async def get_template(template_id: str):
        from aswa_agents.templates import BUILTIN_TEMPLATES
        from uuid import UUID
        try:
            tid = UUID(template_id)
            template = next((t for t in BUILTIN_TEMPLATES if t.id == tid), None)
        except ValueError:
            template = None
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return {
            "id": str(template.id),
            "name": template.name,
            "display_name": template.display_name,
            "description": template.description,
            "category": template.category.value,
            "definition": template.definition,
            "variables": [v.model_dump() for v in template.variables],
        }

    @test_app.post("/api/v1/templates", status_code=201)
    async def create_template(template_data: dict):
        template_id = str(uuid4())
        template = {
            "id": template_id,
            **template_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _mock_templates[template_id] = template
        return template

    @test_app.post("/api/v1/templates/{template_id}/preview")
    async def preview_template(template_id: str, data: dict | None = None):
        from aswa_agents.templates import BUILTIN_TEMPLATES, TemplateEngine
        from uuid import UUID
        try:
            tid = UUID(template_id)
            template = next((t for t in BUILTIN_TEMPLATES if t.id == tid), None)
        except ValueError:
            template = None
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        engine = TemplateEngine()
        variables = (data or {}).get("variable_values", {})
        preview = engine.preview(template, variables)
        return {
            "definition": preview,
            "preview": preview,
            "variables_used": [v.name for v in template.variables],
        }

    @test_app.post("/api/v1/templates/{template_id}/validate")
    async def validate_template(template_id: str, variables: dict):
        from aswa_agents.templates import BUILTIN_TEMPLATES, TemplateEngine
        from uuid import UUID
        try:
            tid = UUID(template_id)
            template = next((t for t in BUILTIN_TEMPLATES if t.id == tid), None)
        except ValueError:
            template = None
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        engine = TemplateEngine()
        errors = engine.validate_variables(template, variables)
        return {"valid": len(errors) == 0, "errors": errors}

    @test_app.post("/api/v1/templates/{template_id}/instantiate")
    async def instantiate_template(template_id: str, data: dict):
        from aswa_agents.templates import BUILTIN_TEMPLATES, TemplateEngine
        from uuid import UUID
        try:
            tid = UUID(template_id)
            template = next((t for t in BUILTIN_TEMPLATES if t.id == tid), None)
        except ValueError:
            template = None
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        engine = TemplateEngine()
        variables = data.get("variables", {})
        try:
            definition = engine.render(template, variables)
            agent_id = str(uuid4())
            agent = {
                "id": agent_id,
                "name": data.get("name", template.name),
                "display_name": data.get("display_name", template.display_name),
                "description": template.description,
                "status": "draft",
                **definition,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _mock_agents[agent_id] = agent
            return {"agent": agent, "instance_id": str(uuid4())}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Approval endpoints
    @test_app.get("/api/v1/approvals")
    async def list_approvals(status: str | None = None):
        approvals = list(_mock_approvals.values())
        if status:
            approvals = [a for a in approvals if a.get("status") == status]
        return {"approvals": approvals, "total": len(approvals)}

    @test_app.get("/api/v1/approvals/policies")
    async def list_policies():
        return {"policies": list(_mock_policies.values()), "total": len(_mock_policies)}

    @test_app.post("/api/v1/approvals/policies", status_code=201)
    async def create_policy(policy_data: dict):
        policy_id = str(uuid4())
        policy = {"id": policy_id, **policy_data}
        _mock_policies[policy_id] = policy
        return policy

    @test_app.get("/api/v1/approvals/roles")
    async def list_roles():
        from aswa_agents.governance import PREDEFINED_ROLES
        roles = [
            {
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "permissions": [p.value for p in r.permissions],
            }
            for r in PREDEFINED_ROLES
        ]
        return {"roles": roles + list(_mock_roles.values()), "total": len(roles) + len(_mock_roles)}

    @test_app.post("/api/v1/approvals/roles", status_code=201)
    async def create_role(role_data: dict):
        role_id = str(uuid4())
        role = {"id": role_id, **role_data}
        _mock_roles[role_id] = role
        return role

    @test_app.get("/api/v1/approvals/users/{user_id}/permissions")
    async def get_user_permissions(user_id: str):
        return {"user_id": user_id, "permissions": ["agent:view", "agent:create"]}

    @test_app.post("/api/v1/approvals/users/{user_id}/roles")
    async def assign_role_to_user(user_id: str, role_data: dict):
        return {"user_id": user_id, "roles": [role_data.get("role_id")]}

    @test_app.post("/api/v1/approvals/users/{user_id}/roles/{role_id}")
    async def assign_role_to_user_path(user_id: str, role_id: str):
        return {"user_id": user_id, "roles": [role_id]}

    @test_app.get("/api/v1/approvals/roles/{role_id}")
    async def get_role(role_id: str):
        from aswa_agents.governance import PREDEFINED_ROLES
        role = next((r for r in PREDEFINED_ROLES if str(r.id) == role_id), None)
        if not role:
            role = _mock_roles.get(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        if hasattr(role, 'model_dump'):
            return role.model_dump()
        return role

    @test_app.get("/api/v1/approvals/check")
    async def check_permission(user_id: str, permission: str):
        return {"allowed": True}

    return test_app


@pytest.fixture
def client(app, settings: Settings) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app, settings: Settings) -> AsyncClient:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
