"""Pytest fixtures for database tests using Testcontainers."""

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from testcontainers.postgres import PostgresContainer

from aswa_common.db.engine import create_engine
from aswa_common.db.models import Base, Tenant, User
from aswa_common.db.session import AsyncSessionFactory


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def postgres_container():
    """Start PostgreSQL container for testing."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
async def engine(postgres_container) -> AsyncEngine:
    """Create async engine connected to test database."""
    database_url = postgres_container.get_connection_url().replace(
        "psycopg2", "asyncpg"
    )
    engine = create_engine(database_url, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    """Create session factory for tests."""
    return AsyncSessionFactory(engine)


@pytest.fixture
async def session(session_factory: AsyncSessionFactory) -> AsyncGenerator[AsyncSession, None]:
    """Create test session with automatic rollback."""
    async with session_factory.session() as session:
        yield session
        # Rollback will happen automatically in the context manager


@pytest.fixture
async def tenant(session: AsyncSession) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        slug="test-tenant",
        settings={},
        status="active",
    )
    session.add(tenant)
    await session.flush()
    await session.refresh(tenant)
    return tenant


@pytest.fixture
async def second_tenant(session: AsyncSession) -> Tenant:
    """Create second test tenant for isolation tests."""
    tenant = Tenant(
        id=uuid4(),
        name="Second Tenant",
        slug="second-tenant",
        settings={},
        status="active",
    )
    session.add(tenant)
    await session.flush()
    await session.refresh(tenant)
    return tenant


@pytest.fixture
async def user(session: AsyncSession, tenant: Tenant) -> User:
    """Create test user."""
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="test@example.com",
        full_name="Test User",
        password_hash="hashed_password",
        role="admin",
        status="active",
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
