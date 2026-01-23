"""Tests for base repository CRUD operations."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models import Tenant, User
from aswa_common.db.repositories.base import BaseRepository, TenantScopedRepository
from aswa_common.exceptions import ValidationError
from aswa_common.models import PageRequest


@pytest.mark.asyncio
async def test_base_repository_create(session: AsyncSession):
    """Test creating entity with base repository."""
    repo = BaseRepository(session, Tenant)

    tenant = Tenant(
        id=uuid4(),
        name="New Tenant",
        slug="new-tenant",
        settings={},
        status="active",
    )

    created = await repo.create(tenant)

    assert created.id == tenant.id
    assert created.name == "New Tenant"
    assert created.slug == "new-tenant"


@pytest.mark.asyncio
async def test_base_repository_get_by_id(session: AsyncSession, tenant: Tenant):
    """Test getting entity by ID."""
    repo = BaseRepository(session, Tenant)

    found = await repo.get_by_id(tenant.id)

    assert found is not None
    assert found.id == tenant.id
    assert found.name == tenant.name


@pytest.mark.asyncio
async def test_base_repository_get_by_id_not_found(session: AsyncSession):
    """Test getting non-existent entity returns None."""
    repo = BaseRepository(session, Tenant)

    found = await repo.get_by_id(uuid4())

    assert found is None


@pytest.mark.asyncio
async def test_base_repository_update(session: AsyncSession, tenant: Tenant):
    """Test updating entity."""
    repo = BaseRepository(session, Tenant)

    # Modify tenant
    tenant.name = "Updated Name"
    tenant.status = "suspended"

    updated = await repo.update(tenant)

    assert updated.name == "Updated Name"
    assert updated.status == "suspended"


@pytest.mark.asyncio
async def test_base_repository_delete(session: AsyncSession, tenant: Tenant):
    """Test deleting entity."""
    repo = BaseRepository(session, Tenant)
    tenant_id = tenant.id

    result = await repo.delete(tenant_id)

    assert result is True

    # Verify deleted
    found = await repo.get_by_id(tenant_id)
    assert found is None


@pytest.mark.asyncio
async def test_base_repository_delete_not_found(session: AsyncSession):
    """Test deleting non-existent entity returns False."""
    repo = BaseRepository(session, Tenant)

    result = await repo.delete(uuid4())

    assert result is False


@pytest.mark.asyncio
async def test_base_repository_exists(session: AsyncSession, tenant: Tenant):
    """Test checking if entity exists."""
    repo = BaseRepository(session, Tenant)

    exists = await repo.exists(tenant.id)

    assert exists is True


@pytest.mark.asyncio
async def test_base_repository_exists_not_found(session: AsyncSession):
    """Test checking if non-existent entity exists."""
    repo = BaseRepository(session, Tenant)

    exists = await repo.exists(uuid4())

    assert exists is False


@pytest.mark.asyncio
async def test_base_repository_get_all(session: AsyncSession):
    """Test getting all entities with pagination."""
    repo = BaseRepository(session, Tenant)

    # Create multiple tenants
    for i in range(5):
        tenant = Tenant(
            id=uuid4(),
            name=f"Tenant {i}",
            slug=f"tenant-{i}",
            settings={},
            status="active",
        )
        await repo.create(tenant)

    # Get first page
    page = PageRequest(page=0, size=3)
    result = await repo.get_all(page)

    assert result.total_elements >= 5
    assert len(result.content) == 3
    assert result.current_page == 0
    assert result.page_size == 3


@pytest.mark.asyncio
async def test_base_repository_get_all_with_sorting(session: AsyncSession):
    """Test getting all entities with sorting."""
    repo = BaseRepository(session, Tenant)

    # Create tenants with different names
    await repo.create(Tenant(id=uuid4(), name="Zebra", slug="zebra", settings={}, status="active"))
    await repo.create(Tenant(id=uuid4(), name="Alpha", slug="alpha", settings={}, status="active"))
    await repo.create(Tenant(id=uuid4(), name="Beta", slug="beta", settings={}, status="active"))

    # Get sorted by name ascending
    page = PageRequest(page=0, size=10, sort_by="name", sort_direction="asc")
    result = await repo.get_all(page)

    names = [t.name for t in result.content]
    assert names[0] == "Alpha"


@pytest.mark.asyncio
async def test_tenant_scoped_repository_get_by_id(session: AsyncSession, tenant: Tenant, user: User):
    """Test tenant-scoped get by ID."""
    repo = TenantScopedRepository(session, User, tenant.id)

    found = await repo.get_by_id(user.id)

    assert found is not None
    assert found.id == user.id
    assert found.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_tenant_scoped_repository_get_by_id_wrong_tenant(
    session: AsyncSession, tenant: Tenant, second_tenant: Tenant, user: User
):
    """Test tenant-scoped get by ID with wrong tenant returns None."""
    # User belongs to tenant, but we're using second_tenant's repo
    repo = TenantScopedRepository(session, User, second_tenant.id)

    found = await repo.get_by_id(user.id)

    assert found is None


@pytest.mark.asyncio
async def test_tenant_scoped_repository_create(session: AsyncSession, tenant: Tenant):
    """Test creating entity with tenant-scoped repository."""
    repo = TenantScopedRepository(session, User, tenant.id)

    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="scoped@example.com",
        full_name="Scoped User",
        password_hash="hash",
        role="user",
        status="active",
    )

    created = await repo.create(user)

    assert created.id == user.id
    assert created.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_tenant_scoped_repository_create_wrong_tenant(
    session: AsyncSession, tenant: Tenant, second_tenant: Tenant
):
    """Test creating entity with mismatched tenant raises error."""
    repo = TenantScopedRepository(session, User, tenant.id)

    # User has second_tenant.id, but repo is for tenant.id
    user = User(
        id=uuid4(),
        tenant_id=second_tenant.id,
        email="wrong@example.com",
        full_name="Wrong Tenant User",
        password_hash="hash",
        role="user",
        status="active",
    )

    with pytest.raises(ValidationError) as exc_info:
        await repo.create(user)

    assert "tenant_id does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tenant_scoped_repository_get_all(
    session: AsyncSession, tenant: Tenant, second_tenant: Tenant
):
    """Test get all only returns entities for the tenant."""
    repo = TenantScopedRepository(session, User, tenant.id)

    # Create users for different tenants
    user1 = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="user1@example.com",
        full_name="User 1",
        password_hash="hash",
        role="user",
        status="active",
    )
    user2 = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email="user2@example.com",
        full_name="User 2",
        password_hash="hash",
        role="user",
        status="active",
    )
    user3 = User(
        id=uuid4(),
        tenant_id=second_tenant.id,
        email="user3@example.com",
        full_name="User 3",
        password_hash="hash",
        role="user",
        status="active",
    )

    session.add_all([user1, user2, user3])
    await session.flush()

    # Get all for tenant
    page = PageRequest(page=0, size=10)
    result = await repo.get_all(page)

    # Should only have users from tenant, not second_tenant
    user_ids = {u.id for u in result.content}
    assert user1.id in user_ids
    assert user2.id in user_ids
    assert user3.id not in user_ids


@pytest.mark.asyncio
async def test_tenant_scoped_repository_delete(session: AsyncSession, tenant: Tenant, user: User):
    """Test deleting entity with tenant scope."""
    repo = TenantScopedRepository(session, User, tenant.id)
    user_id = user.id

    result = await repo.delete(user_id)

    assert result is True

    # Verify deleted
    found = await repo.get_by_id(user_id)
    assert found is None


@pytest.mark.asyncio
async def test_tenant_scoped_repository_delete_wrong_tenant(
    session: AsyncSession, tenant: Tenant, second_tenant: Tenant, user: User
):
    """Test deleting entity from wrong tenant returns False."""
    # User belongs to tenant, but we're using second_tenant's repo
    repo = TenantScopedRepository(session, User, second_tenant.id)

    result = await repo.delete(user.id)

    assert result is False

    # Verify user still exists
    correct_repo = TenantScopedRepository(session, User, tenant.id)
    found = await correct_repo.get_by_id(user.id)
    assert found is not None


@pytest.mark.asyncio
async def test_tenant_scoped_repository_exists(session: AsyncSession, tenant: Tenant, user: User):
    """Test exists check with tenant scope."""
    repo = TenantScopedRepository(session, User, tenant.id)

    exists = await repo.exists(user.id)

    assert exists is True


@pytest.mark.asyncio
async def test_tenant_scoped_repository_exists_wrong_tenant(
    session: AsyncSession, tenant: Tenant, second_tenant: Tenant, user: User
):
    """Test exists check with wrong tenant returns False."""
    repo = TenantScopedRepository(session, User, second_tenant.id)

    exists = await repo.exists(user.id)

    assert exists is False
