"""FastAPI dependencies for injection."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.config import get_settings, Settings
from aswa_agents.persistence.database import get_session


async def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_session():
        yield session


async def get_current_tenant(
    authorization: Annotated[str, Header()],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> str:
    """Extract tenant ID from JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Tenant ID not in token")
        return tenant_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    authorization: Annotated[str, Header()],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    """Extract user info from JWT token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
