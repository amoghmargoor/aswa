"""Connection management endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

from aswa_connector.dependencies import DbSession, TenantCtx, Provider
from aswa_connector.framework.models import (
    ConnectorType,
    ConnectionConfig,
    ConnectionStatus,
    OAuthCredentials,
)

logger = get_logger(__name__)

router = APIRouter()


# Request/Response models

class ConnectorInfo(BaseModel):
    """Connector information."""

    type: str
    name: str
    description: str
    icon_url: str | None = None
    auth_type: str
    scopes: list[str] = Field(default_factory=list)


class CreateConnectionRequest(BaseModel):
    """Request to create a connection."""

    connector_type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any]  # OAuth tokens or API keys
    sync_schedule: str | None = None  # Cron expression
    sync_mode: str = "incremental"


class UpdateConnectionRequest(BaseModel):
    """Request to update a connection."""

    name: str | None = None
    config: dict[str, Any] | None = None
    sync_schedule: str | None = None
    sync_mode: str | None = None


class ConnectionResponse(BaseModel):
    """Connection response."""

    id: UUID
    connector_type: str
    name: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    sync_schedule: str | None = None
    sync_mode: str = "incremental"
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionListResponse(BaseModel):
    """Paginated connection list."""

    content: list[ConnectionResponse]
    total_elements: int
    total_pages: int
    current_page: int
    page_size: int


class ConnectionTestResponse(BaseModel):
    """Connection test result."""

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# Endpoints

@router.get("/connectors", response_model=list[ConnectorInfo])
async def list_connectors(
    provider: Provider,
) -> list[ConnectorInfo]:
    """List available connector types."""
    definitions = await provider.list_available_connectors()

    return [
        ConnectorInfo(
            type=d.type.value,
            name=d.name,
            description=d.description,
            icon_url=d.icon_url,
            auth_type=d.auth_type,
            scopes=d.scopes,
        )
        for d in definitions
    ]


@router.get("/connectors/{connector_type}", response_model=ConnectorInfo)
async def get_connector(
    connector_type: str,
    provider: Provider,
) -> ConnectorInfo:
    """Get connector definition."""
    definition = await provider.get_connector_definition(connector_type)

    if not definition:
        raise HTTPException(status_code=404, detail="Connector not found")

    return ConnectorInfo(
        type=definition.type.value,
        name=definition.name,
        description=definition.description,
        icon_url=definition.icon_url,
        auth_type=definition.auth_type,
        scopes=definition.scopes,
    )


@router.post("/connections", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    request: CreateConnectionRequest,
    tenant: TenantCtx,
    db: DbSession,
    provider: Provider,
) -> ConnectionResponse:
    """Create a new data source connection."""
    logger.info(
        f"Creating connection: tenant={tenant['tenant_id']}, "
        f"type={request.connector_type}, name={request.name}"
    )

    try:
        connector_type = ConnectorType(request.connector_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown connector type: {request.connector_type}",
        )

    # Build credentials
    credentials = OAuthCredentials(
        access_token=request.credentials.get("access_token", ""),
        refresh_token=request.credentials.get("refresh_token"),
        expires_at=request.credentials.get("expires_at"),
    )

    config = ConnectionConfig(
        connector_type=connector_type,
        name=request.name,
        credentials=credentials,
        config=request.config,
        sync_schedule=request.sync_schedule,
        sync_mode=request.sync_mode,
    )

    # Create connection via provider
    connection = await provider.create_connection(
        tenant_id=tenant["tenant_id"],
        config=config,
    )

    # Save to database
    from aswa_connector.models.connection import ConnectionModel

    db_connection = ConnectionModel(
        id=connection.id,
        tenant_id=connection.tenant_id,
        connector_type=connection.connector_type.value,
        name=connection.name,
        status=connection.status.value,
        config=connection.config,
        sync_schedule=connection.sync_schedule,
        sync_mode=connection.sync_mode,
        provider_source_id=connection.provider_source_id,
        provider_connection_id=connection.provider_connection_id,
    )
    db.add(db_connection)
    await db.flush()
    await db.refresh(db_connection)

    # Store encrypted tokens
    from aswa_connector.framework.oauth import TokenStore
    from aswa_connector.framework.oauth.models import OAuthTokens

    token_store = TokenStore()
    tokens = OAuthTokens(
        access_token=request.credentials.get("access_token", ""),
        refresh_token=request.credentials.get("refresh_token"),
    )
    await token_store.store_tokens(
        db=db,
        connection_id=connection.id,
        tenant_id=tenant["tenant_id"],
        tokens=tokens,
    )

    return ConnectionResponse(
        id=db_connection.id,
        connector_type=db_connection.connector_type,
        name=db_connection.name,
        status=db_connection.status,
        config=db_connection.config or {},
        sync_schedule=db_connection.sync_schedule,
        sync_mode=db_connection.sync_mode,
        last_sync_at=db_connection.last_sync_at,
        next_sync_at=db_connection.next_sync_at,
        error_message=db_connection.error_message,
        created_at=db_connection.created_at,
        updated_at=db_connection.updated_at,
    )


@router.get("/connections", response_model=ConnectionListResponse)
async def list_connections(
    tenant: TenantCtx,
    db: DbSession,
    connector_type: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
) -> ConnectionListResponse:
    """List connections for the tenant."""
    from sqlalchemy import select, func
    from aswa_connector.models.connection import ConnectionModel

    # Build query
    query = select(ConnectionModel).where(
        ConnectionModel.tenant_id == tenant["tenant_id"]
    )

    if connector_type:
        query = query.where(ConnectionModel.connector_type == connector_type)
    if status:
        query = query.where(ConnectionModel.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset(page * size).limit(size)
    query = query.order_by(ConnectionModel.created_at.desc())

    result = await db.execute(query)
    connections = result.scalars().all()

    return ConnectionListResponse(
        content=[
            ConnectionResponse(
                id=c.id,
                connector_type=c.connector_type,
                name=c.name,
                status=c.status,
                config=c.config or {},
                sync_schedule=c.sync_schedule,
                sync_mode=c.sync_mode,
                last_sync_at=c.last_sync_at,
                next_sync_at=c.next_sync_at,
                error_message=c.error_message,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in connections
        ],
        total_elements=total,
        total_pages=(total + size - 1) // size,
        current_page=page,
        page_size=size,
    )


@router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: UUID,
    tenant: TenantCtx,
    db: DbSession,
) -> ConnectionResponse:
    """Get connection details."""
    from sqlalchemy import select
    from aswa_connector.models.connection import ConnectionModel

    query = select(ConnectionModel).where(
        ConnectionModel.id == connection_id,
        ConnectionModel.tenant_id == tenant["tenant_id"],
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return ConnectionResponse(
        id=connection.id,
        connector_type=connection.connector_type,
        name=connection.name,
        status=connection.status,
        config=connection.config or {},
        sync_schedule=connection.sync_schedule,
        sync_mode=connection.sync_mode,
        last_sync_at=connection.last_sync_at,
        next_sync_at=connection.next_sync_at,
        error_message=connection.error_message,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.put("/connections/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: UUID,
    request: UpdateConnectionRequest,
    tenant: TenantCtx,
    db: DbSession,
) -> ConnectionResponse:
    """Update a connection."""
    from sqlalchemy import select
    from aswa_connector.models.connection import ConnectionModel

    query = select(ConnectionModel).where(
        ConnectionModel.id == connection_id,
        ConnectionModel.tenant_id == tenant["tenant_id"],
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Update fields
    if request.name is not None:
        connection.name = request.name
    if request.config is not None:
        connection.config = request.config
    if request.sync_schedule is not None:
        connection.sync_schedule = request.sync_schedule
    if request.sync_mode is not None:
        connection.sync_mode = request.sync_mode

    connection.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return ConnectionResponse(
        id=connection.id,
        connector_type=connection.connector_type,
        name=connection.name,
        status=connection.status,
        config=connection.config or {},
        sync_schedule=connection.sync_schedule,
        sync_mode=connection.sync_mode,
        last_sync_at=connection.last_sync_at,
        next_sync_at=connection.next_sync_at,
        error_message=connection.error_message,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID,
    tenant: TenantCtx,
    db: DbSession,
    provider: Provider,
) -> None:
    """Delete a connection."""
    from sqlalchemy import select, delete
    from aswa_connector.models.connection import ConnectionModel

    query = select(ConnectionModel).where(
        ConnectionModel.id == connection_id,
        ConnectionModel.tenant_id == tenant["tenant_id"],
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Delete from Airbyte
    if connection.provider_source_id:
        try:
            await provider.delete_airbyte_source(connection.provider_source_id)
        except Exception as e:
            logger.warning(f"Failed to delete Airbyte source: {e}")

    # Delete tokens
    from aswa_connector.models.oauth_token import OAuthTokenModel

    await db.execute(
        delete(OAuthTokenModel).where(
            OAuthTokenModel.connection_id == connection_id,
            OAuthTokenModel.tenant_id == tenant["tenant_id"],
        )
    )

    # Delete connection
    await db.execute(
        delete(ConnectionModel).where(ConnectionModel.id == connection_id)
    )


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: UUID,
    tenant: TenantCtx,
    db: DbSession,
    provider: Provider,
) -> ConnectionTestResponse:
    """Test a connection."""
    from sqlalchemy import select
    from aswa_connector.models.connection import ConnectionModel

    query = select(ConnectionModel).where(
        ConnectionModel.id == connection_id,
        ConnectionModel.tenant_id == tenant["tenant_id"],
    )
    result = await db.execute(query)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if not connection.provider_source_id:
        raise HTTPException(
            status_code=400,
            detail="Connection has no provider source",
        )

    test_result = await provider.test_airbyte_source(connection.provider_source_id)

    # Update connection status based on test
    if test_result.success:
        connection.status = ConnectionStatus.ACTIVE.value
        connection.error_message = None
    else:
        connection.status = ConnectionStatus.ERROR.value
        connection.error_message = test_result.message

    connection.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return ConnectionTestResponse(
        success=test_result.success,
        message=test_result.message,
        details=test_result.details,
    )
