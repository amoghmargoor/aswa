import uuid
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import httpx
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.models.webhook import (
    WebhookDB,
    WebhookDeliveryDB,
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookDeliveryResponse,
    WebhookEvent,
    WebhookEventType,
    DeliveryStatus,
)
from aswa_integrations.models.integration import Base
from aswa_integrations.services.credential_manager import CredentialManager

logger = structlog.get_logger()


class WebhookManager:
    """Manages webhook registrations and deliveries."""

    def __init__(self):
        self.settings = get_settings()
        self.credential_manager = CredentialManager()
        self._engine = None
        self._session_factory = None

    async def initialize(self) -> None:
        """Initialize the webhook manager."""
        self._engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
        )

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        await self.credential_manager.initialize()
        logger.info("Webhook manager initialized")

    async def close(self) -> None:
        """Close connections."""
        await self.credential_manager.close()
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Webhook manager not initialized")
        return self._session_factory()

    async def create_webhook(
        self,
        tenant_id: str,
        data: WebhookCreate,
    ) -> WebhookResponse:
        """Create a new webhook.

        Args:
            tenant_id: Tenant identifier
            data: Webhook creation data

        Returns:
            Created webhook
        """
        webhook_id = str(uuid.uuid4())

        # Store secret if provided
        secret_id = None
        if data.secret:
            secret_id = f"webhook:{webhook_id}"
            await self.credential_manager.store_credentials(
                secret_id,
                {"secret": data.secret},
            )

        webhook = WebhookDB(
            id=webhook_id,
            tenant_id=tenant_id,
            name=data.name,
            url=str(data.url),
            secret=secret_id,
            events=[e.value for e in data.events],
            headers=data.headers,
        )

        async with self._get_session() as session:
            session.add(webhook)
            await session.commit()
            await session.refresh(webhook)

        logger.info(
            "Webhook created",
            webhook_id=webhook_id,
            tenant_id=tenant_id,
        )

        return WebhookResponse.model_validate(webhook)

    async def get_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
    ) -> WebhookResponse | None:
        """Get a webhook by ID.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier

        Returns:
            Webhook or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if webhook:
                return WebhookResponse.model_validate(webhook)
            return None

    async def list_webhooks(
        self,
        tenant_id: str,
        event_type: WebhookEventType | None = None,
        is_active: bool | None = None,
    ) -> list[WebhookResponse]:
        """List webhooks for a tenant.

        Args:
            tenant_id: Tenant identifier
            event_type: Optional event type filter
            is_active: Optional active status filter

        Returns:
            List of webhooks
        """
        async with self._get_session() as session:
            query = select(WebhookDB).where(WebhookDB.tenant_id == tenant_id)

            if is_active is not None:
                query = query.where(WebhookDB.is_active == is_active)

            result = await session.execute(query)
            webhooks = result.scalars().all()

            # Filter by event type if specified
            if event_type:
                webhooks = [
                    w for w in webhooks
                    if event_type.value in w.events
                ]

            return [WebhookResponse.model_validate(w) for w in webhooks]

    async def update_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
        data: WebhookUpdate,
    ) -> WebhookResponse | None:
        """Update a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier
            data: Update data

        Returns:
            Updated webhook or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                return None

            if data.name is not None:
                webhook.name = data.name
            if data.url is not None:
                webhook.url = str(data.url)
            if data.events is not None:
                webhook.events = [e.value for e in data.events]
            if data.headers is not None:
                webhook.headers = data.headers
            if data.is_active is not None:
                webhook.is_active = data.is_active

            # Update secret if provided
            if data.secret is not None:
                secret_id = webhook.secret or f"webhook:{webhook_id}"
                await self.credential_manager.store_credentials(
                    secret_id,
                    {"secret": data.secret},
                )
                webhook.secret = secret_id

            webhook.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(webhook)

            return WebhookResponse.model_validate(webhook)

    async def delete_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier

        Returns:
            True if deleted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                return False

            # Delete secret
            if webhook.secret:
                await self.credential_manager.delete_credentials(webhook.secret)

            await session.delete(webhook)
            await session.commit()

            return True

    async def dispatch_event(
        self,
        event: WebhookEvent,
    ) -> list[str]:
        """Dispatch an event to all matching webhooks.

        Args:
            event: Event to dispatch

        Returns:
            List of delivery IDs
        """
        # Find matching webhooks
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.tenant_id == event.tenant_id,
                    WebhookDB.is_active == True,
                )
            )
            webhooks = result.scalars().all()

        # Filter by event type
        matching = [
            w for w in webhooks
            if event.type.value in w.events or not w.events
        ]

        # Create delivery records
        delivery_ids = []
        for webhook in matching:
            delivery_id = await self._create_delivery(webhook, event)
            delivery_ids.append(delivery_id)

        logger.info(
            "Event dispatched",
            event_type=event.type,
            webhook_count=len(matching),
        )

        return delivery_ids

    async def _create_delivery(
        self,
        webhook: WebhookDB,
        event: WebhookEvent,
    ) -> str:
        """Create a delivery record and attempt delivery.

        Args:
            webhook: Target webhook
            event: Event to deliver

        Returns:
            Delivery ID
        """
        delivery_id = str(uuid.uuid4())

        payload = {
            "id": event.id,
            "type": event.type.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
        }

        delivery = WebhookDeliveryDB(
            id=delivery_id,
            webhook_id=webhook.id,
            event_type=event.type.value,
            payload=payload,
            status=DeliveryStatus.PENDING,
        )

        async with self._get_session() as session:
            session.add(delivery)
            await session.commit()

        # Attempt delivery
        await self._deliver(webhook, delivery)

        return delivery_id

    async def _deliver(
        self,
        webhook: WebhookDB,
        delivery: WebhookDeliveryDB,
    ) -> None:
        """Attempt to deliver a webhook.

        Args:
            webhook: Target webhook
            delivery: Delivery record
        """
        # Get secret if configured
        secret = None
        if webhook.secret:
            creds = await self.credential_manager.get_credentials(webhook.secret)
            if creds:
                secret = creds.get("secret")

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ASWA-Webhook/1.0",
            "X-Webhook-ID": str(webhook.id),
            "X-Delivery-ID": str(delivery.id),
            **webhook.headers,
        }

        # Add signature if secret is configured
        payload_bytes = json.dumps(delivery.payload, sort_keys=True).encode()
        if secret:
            signature = hmac.new(
                secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-ASWA-Signature"] = f"sha256={signature}"

        # Attempt delivery
        async with self._get_session() as session:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        webhook.url,
                        content=payload_bytes,
                        headers=headers,
                    )

                    delivery.response_status = response.status_code
                    delivery.response_body = response.text[:1000]  # Limit size
                    delivery.attempt_count += 1

                    if response.is_success:
                        delivery.status = DeliveryStatus.DELIVERED
                        delivery.delivered_at = datetime.utcnow()

                        # Update webhook stats
                        await session.execute(
                            update(WebhookDB)
                            .where(WebhookDB.id == webhook.id)
                            .values(
                                total_deliveries=WebhookDB.total_deliveries + 1,
                                successful_deliveries=WebhookDB.successful_deliveries + 1,
                                last_delivery_at=datetime.utcnow(),
                            )
                        )
                    else:
                        await self._handle_failure(
                            session, webhook, delivery,
                            f"HTTP {response.status_code}",
                        )

            except Exception as e:
                delivery.attempt_count += 1
                await self._handle_failure(session, webhook, delivery, str(e))

            session.add(delivery)
            await session.commit()

    async def _handle_failure(
        self,
        session: AsyncSession,
        webhook: WebhookDB,
        delivery: WebhookDeliveryDB,
        error: str,
    ) -> None:
        """Handle delivery failure.

        Args:
            session: Database session
            webhook: Target webhook
            delivery: Delivery record
            error: Error message
        """
        delivery.error = error

        if delivery.attempt_count < delivery.max_attempts:
            # Schedule retry with exponential backoff
            delay = 60 * (2 ** (delivery.attempt_count - 1))  # 1, 2, 4 minutes
            delivery.status = DeliveryStatus.RETRYING
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

            logger.info(
                "Webhook delivery scheduled for retry",
                delivery_id=str(delivery.id),
                attempt=delivery.attempt_count,
                next_retry=delivery.next_retry_at,
            )
        else:
            delivery.status = DeliveryStatus.FAILED

            # Update webhook stats
            await session.execute(
                update(WebhookDB)
                .where(WebhookDB.id == webhook.id)
                .values(
                    total_deliveries=WebhookDB.total_deliveries + 1,
                    failed_deliveries=WebhookDB.failed_deliveries + 1,
                    last_error=error,
                )
            )

            logger.error(
                "Webhook delivery failed permanently",
                delivery_id=str(delivery.id),
                error=error,
            )

    async def retry_pending_deliveries(self) -> int:
        """Retry pending deliveries that are due.

        Returns:
            Number of retries attempted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDeliveryDB).where(
                    WebhookDeliveryDB.status == DeliveryStatus.RETRYING,
                    WebhookDeliveryDB.next_retry_at <= datetime.utcnow(),
                )
            )
            deliveries = result.scalars().all()

            count = 0
            for delivery in deliveries:
                # Get webhook
                wh_result = await session.execute(
                    select(WebhookDB).where(WebhookDB.id == delivery.webhook_id)
                )
                webhook = wh_result.scalar_one_or_none()

                if webhook and webhook.is_active:
                    await self._deliver(webhook, delivery)
                    count += 1

            return count

    async def get_delivery_history(
        self,
        tenant_id: str,
        webhook_id: str,
        limit: int = 50,
    ) -> list[WebhookDeliveryResponse]:
        """Get delivery history for a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier
            limit: Maximum number of records

        Returns:
            List of deliveries
        """
        # Verify webhook ownership
        webhook = await self.get_webhook(tenant_id, webhook_id)
        if not webhook:
            return []

        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDeliveryDB)
                .where(WebhookDeliveryDB.webhook_id == webhook_id)
                .order_by(WebhookDeliveryDB.created_at.desc())
                .limit(limit)
            )
            deliveries = result.scalars().all()

            return [
                WebhookDeliveryResponse.model_validate(d)
                for d in deliveries
            ]
