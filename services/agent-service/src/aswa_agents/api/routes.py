"""API route definitions for Agent Service."""

from fastapi import APIRouter

from aswa_agents.api.endpoints import (
    agents,
    executions,
    approvals,
    templates,
    actions,
    generation,
)


router = APIRouter()

# Include all endpoint routers
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(executions.router, prefix="/executions", tags=["executions"])
router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(actions.router, prefix="/actions", tags=["actions"])
router.include_router(generation.router, prefix="/generate", tags=["generation"])
