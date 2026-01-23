"""Base repository classes for database operations."""

import math
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models.base import Base
from aswa_common.exceptions import AswaError, ErrorCode, ValidationError
from aswa_common.logging import get_logger
from aswa_common.models import PageRequest, PageResponse

T = TypeVar("T", bound=Base)

logger = get_logger(__name__)


class BaseRepository(Generic[T]):
    """Base repository with generic CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        """Initialize repository.

        Args:
            session: Async database session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> T | None:
        """Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity if found, None otherwise
        """
        logger.debug(f"Fetching {self.model.__name__} by id={id}")
        return await self.session.get(self.model, id)

    async def get_all(self, page: PageRequest) -> PageResponse[T]:
        """Get all entities with pagination.

        Args:
            page: Pagination request

        Returns:
            Paginated response
        """
        logger.debug(f"Fetching all {self.model.__name__} with pagination: page={page.page}, size={page.size}")

        # Count total
        count_stmt = select(func.count()).select_from(self.model)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Build query
        stmt = select(self.model)

        # Apply sorting if specified
        if page.sort_by:
            if hasattr(self.model, page.sort_by):
                column = getattr(self.model, page.sort_by)
                stmt = stmt.order_by(
                    column.desc() if page.sort_direction == "desc" else column.asc()
                )

        # Apply pagination
        stmt = stmt.offset(page.page * page.size).limit(page.size)

        # Execute
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        total_pages = math.ceil(total / page.size) if page.size > 0 else 0

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=total_pages,
            current_page=page.page,
            page_size=page.size,
        )

    async def create(self, entity: T) -> T:
        """Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity

        Raises:
            ValidationError: If entity already exists or validation fails
        """
        try:
            logger.debug(f"Creating {self.model.__name__}: {entity}")
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error creating {self.model.__name__}", exc_info=e)
            raise ValidationError(
                f"Failed to create {self.model.__name__}: constraint violation",
                {"error": str(e.orig)},
            ) from e

    async def update(self, entity: T) -> T:
        """Update existing entity.

        Args:
            entity: Entity to update

        Returns:
            Updated entity

        Raises:
            ValidationError: If update fails
        """
        try:
            logger.debug(f"Updating {self.model.__name__}: {entity}")
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Integrity error updating {self.model.__name__}", exc_info=e)
            raise ValidationError(
                f"Failed to update {self.model.__name__}: constraint violation",
                {"error": str(e.orig)},
            ) from e

    async def delete(self, id: UUID) -> bool:
        """Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        logger.debug(f"Deleting {self.model.__name__} by id={id}")
        entity = await self.get_by_id(id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False

    async def exists(self, id: UUID) -> bool:
        """Check if entity exists by ID.

        Args:
            id: Entity ID

        Returns:
            True if exists, False otherwise
        """
        logger.debug(f"Checking existence of {self.model.__name__} by id={id}")
        stmt = select(func.count()).where(self.model.id == id)
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        return count > 0


class TenantScopedRepository(BaseRepository[T]):
    """Repository that enforces tenant isolation."""

    def __init__(self, session: AsyncSession, model: type[T], tenant_id: UUID) -> None:
        """Initialize tenant-scoped repository.

        Args:
            session: Async database session
            model: SQLAlchemy model class
            tenant_id: Tenant ID for isolation
        """
        super().__init__(session, model)
        self.tenant_id = tenant_id

    async def get_by_id(self, id: UUID) -> T | None:
        """Get entity by ID within tenant scope.

        Args:
            id: Entity ID

        Returns:
            Entity if found and belongs to tenant, None otherwise
        """
        logger.debug(f"Fetching {self.model.__name__} by id={id} for tenant={self.tenant_id}")
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.tenant_id == self.tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, page: PageRequest) -> PageResponse[T]:
        """Get all entities within tenant scope with pagination.

        Args:
            page: Pagination request

        Returns:
            Paginated response with tenant-scoped entities
        """
        logger.debug(
            f"Fetching all {self.model.__name__} for tenant={self.tenant_id} with pagination: page={page.page}, size={page.size}"
        )

        # Count total for tenant
        count_stmt = select(func.count()).select_from(self.model).where(
            self.model.tenant_id == self.tenant_id
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Build query with tenant filter
        stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)

        # Apply sorting if specified
        if page.sort_by:
            if hasattr(self.model, page.sort_by):
                column = getattr(self.model, page.sort_by)
                stmt = stmt.order_by(
                    column.desc() if page.sort_direction == "desc" else column.asc()
                )

        # Apply pagination
        stmt = stmt.offset(page.page * page.size).limit(page.size)

        # Execute
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        total_pages = math.ceil(total / page.size) if page.size > 0 else 0

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=total_pages,
            current_page=page.page,
            page_size=page.size,
        )

    async def create(self, entity: T) -> T:
        """Create new entity with tenant assignment.

        Args:
            entity: Entity to create

        Returns:
            Created entity

        Raises:
            ValidationError: If tenant_id doesn't match or validation fails
        """
        if entity.tenant_id != self.tenant_id:
            raise ValidationError(
                "Entity tenant_id does not match repository tenant_id",
                {"entity_tenant_id": str(entity.tenant_id), "repo_tenant_id": str(self.tenant_id)},
            )
        return await super().create(entity)

    async def delete(self, id: UUID) -> bool:
        """Delete entity by ID within tenant scope.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found or not in tenant
        """
        logger.debug(f"Deleting {self.model.__name__} by id={id} for tenant={self.tenant_id}")
        entity = await self.get_by_id(id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False

    async def exists(self, id: UUID) -> bool:
        """Check if entity exists by ID within tenant scope.

        Args:
            id: Entity ID

        Returns:
            True if exists and belongs to tenant, False otherwise
        """
        logger.debug(
            f"Checking existence of {self.model.__name__} by id={id} for tenant={self.tenant_id}"
        )
        stmt = select(func.count()).where(
            self.model.id == id,
            self.model.tenant_id == self.tenant_id,
        )
        result = await self.session.execute(stmt)
        count = result.scalar_one()
        return count > 0
