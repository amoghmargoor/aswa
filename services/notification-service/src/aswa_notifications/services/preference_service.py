from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from aswa_notifications.models.preference import (
    NotificationPreferenceDB,
    PreferenceUpdate,
    PreferenceResponse,
)

logger = structlog.get_logger()


class PreferenceService:
    """Manages notification preferences."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        return self._session_factory()

    async def get_preferences(
        self,
        tenant_id: str,
        user_id: str,
    ) -> PreferenceResponse | None:
        """Get user preferences.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Preferences or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            pref = result.scalar_one_or_none()

            if pref:
                return PreferenceResponse.model_validate(pref)
            return None

    async def create_preferences(
        self,
        tenant_id: str,
        user_id: str,
        email_address: str | None = None,
    ) -> PreferenceResponse:
        """Create default preferences for a user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            email_address: Optional email address

        Returns:
            Created preferences
        """
        pref = NotificationPreferenceDB(
            tenant_id=tenant_id,
            user_id=user_id,
            email_address=email_address,
        )

        async with self._get_session() as session:
            session.add(pref)
            await session.commit()
            await session.refresh(pref)

            return PreferenceResponse.model_validate(pref)

    async def update_preferences(
        self,
        tenant_id: str,
        user_id: str,
        updates: PreferenceUpdate,
    ) -> PreferenceResponse | None:
        """Update user preferences.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            updates: Preference updates

        Returns:
            Updated preferences or None
        """
        update_data = updates.model_dump(exclude_unset=True)
        if not update_data:
            return await self.get_preferences(tenant_id, user_id)

        update_data["updated_at"] = datetime.utcnow()

        async with self._get_session() as session:
            result = await session.execute(
                update(NotificationPreferenceDB)
                .where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
                .values(**update_data)
                .returning(NotificationPreferenceDB)
            )
            await session.commit()

            pref = result.scalar_one_or_none()
            if pref:
                return PreferenceResponse.model_validate(pref)
            return None

    async def register_push_token(
        self,
        tenant_id: str,
        user_id: str,
        token: str,
        device_type: str = "unknown",
    ) -> bool:
        """Register a push notification token.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            token: Push token
            device_type: Device type (ios, android, web)

        Returns:
            True if registered
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            pref = result.scalar_one_or_none()

            if not pref:
                return False

            tokens = pref.push_tokens or []

            # Check if token already exists
            existing = next((t for t in tokens if t.get("token") == token), None)
            if existing:
                existing["updated_at"] = datetime.utcnow().isoformat()
            else:
                tokens.append({
                    "token": token,
                    "device_type": device_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                })

            await session.execute(
                update(NotificationPreferenceDB)
                .where(NotificationPreferenceDB.id == pref.id)
                .values(push_tokens=tokens)
            )
            await session.commit()

            return True

    async def unregister_push_token(
        self,
        tenant_id: str,
        user_id: str,
        token: str,
    ) -> bool:
        """Unregister a push notification token.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            token: Push token to remove

        Returns:
            True if unregistered
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            pref = result.scalar_one_or_none()

            if not pref:
                return False

            tokens = pref.push_tokens or []
            tokens = [t for t in tokens if t.get("token") != token]

            await session.execute(
                update(NotificationPreferenceDB)
                .where(NotificationPreferenceDB.id == pref.id)
                .values(push_tokens=tokens)
            )
            await session.commit()

            return True
