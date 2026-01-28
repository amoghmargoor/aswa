# Task 6.1.1: Integration Service - Setup

## Context

You are building the ASWA integration service at `/services/integration-service/`. This service manages connections to external systems (Jira, webhooks, notifications).

## Objective

Create an integration service that:
1. Provides a unified API for external integrations
2. Manages connection credentials securely
3. Handles rate limiting and retries
4. Supports multiple integration types
5. Provides health monitoring for connections

## Requirements

### 1. Create service structure

```
/services/integration-service/
├── src/
│   └── aswa_integrations/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py
│       │   └── dependencies.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── integration.py
│       │   └── webhook.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── integration_manager.py
│       │   ├── credential_manager.py
│       │   └── health_checker.py
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── jira.py
│       │   └── webhook.py
│       └── utils/
│           ├── __init__.py
│           ├── encryption.py
│           └── rate_limiter.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_integration_manager.py
├── pyproject.toml
└── Dockerfile
```

### 2. Create `/services/integration-service/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aswa-integrations"
version = "0.1.0"
description = "ASWA Integration Service"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "httpx>=0.25.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "redis>=5.0.0",
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "cryptography>=41.0.0",
    "tenacity>=8.2.0",
    "structlog>=23.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 3. Create `/services/integration-service/src/aswa_integrations/config.py`
```python
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Integration service settings."""

    # Service
    service_name: str = "aswa-integrations"
    environment: str = "development"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8004

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://aswa:aswa@localhost:5432/aswa_integrations"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/3"

    # Encryption
    encryption_key: str = Field(
        default="change-me-in-production-32-chars!"
    )

    # Rate limiting
    default_rate_limit: int = 100  # requests per minute
    rate_limit_window: int = 60  # seconds

    # Health check
    health_check_interval: int = 60  # seconds
    health_check_timeout: int = 10  # seconds

    # API Gateway
    api_gateway_url: str = "http://localhost:8000"

    model_config = {
        "env_prefix": "INTEGRATIONS_",
        "env_file": ".env",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4. Create `/services/integration-service/src/aswa_integrations/models/integration.py`
```python
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class IntegrationType(str, Enum):
    """Supported integration types."""
    JIRA = "jira"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class IntegrationDB(Base):
    """Database model for integrations."""

    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(SQLEnum(IntegrationType), nullable=False)
    status = Column(SQLEnum(IntegrationStatus), default=IntegrationStatus.PENDING)
    config = Column(JSON, default={})
    credentials_id = Column(String, nullable=True)  # Reference to encrypted credentials
    last_health_check = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_enabled = Column(Boolean, default=True)


class IntegrationCreate(BaseModel):
    """Schema for creating an integration."""

    name: str = Field(..., min_length=1, max_length=255)
    type: IntegrationType
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, str] | None = None


class IntegrationUpdate(BaseModel):
    """Schema for updating an integration."""

    name: str | None = None
    config: dict[str, Any] | None = None
    credentials: dict[str, str] | None = None
    is_enabled: bool | None = None


class IntegrationResponse(BaseModel):
    """Schema for integration response."""

    id: str
    tenant_id: str
    name: str
    type: IntegrationType
    status: IntegrationStatus
    config: dict[str, Any]
    last_health_check: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    is_enabled: bool

    model_config = {"from_attributes": True}


class IntegrationHealth(BaseModel):
    """Integration health status."""

    integration_id: str
    status: IntegrationStatus
    latency_ms: float | None = None
    last_check: datetime
    error: str | None = None
```

### 5. Create `/services/integration-service/src/aswa_integrations/services/credential_manager.py`
```python
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import redis.asyncio as redis
import structlog

from aswa_integrations.config import get_settings

logger = structlog.get_logger()


class CredentialManager:
    """Manages encrypted storage of integration credentials."""

    def __init__(self):
        self.settings = get_settings()
        self._fernet: Fernet | None = None
        self._redis: redis.Redis | None = None

    async def initialize(self) -> None:
        """Initialize the credential manager."""
        # Derive encryption key
        key = self._derive_key(self.settings.encryption_key)
        self._fernet = Fernet(key)

        # Connect to Redis
        self._redis = redis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        logger.info("Credential manager initialized")

    async def close(self) -> None:
        """Close connections."""
        if self._redis:
            await self._redis.close()

    def _derive_key(self, password: str) -> bytes:
        """Derive a Fernet key from a password."""
        salt = b"aswa-integrations-salt"  # In production, use a random salt per credential
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    async def store_credentials(
        self,
        credential_id: str,
        credentials: dict[str, str],
        ttl: int | None = None,
    ) -> None:
        """Store encrypted credentials.

        Args:
            credential_id: Unique identifier for the credentials
            credentials: Dictionary of credential key-value pairs
            ttl: Optional TTL in seconds
        """
        if not self._fernet or not self._redis:
            raise RuntimeError("Credential manager not initialized")

        # Encrypt credentials
        json_data = json.dumps(credentials)
        encrypted = self._fernet.encrypt(json_data.encode())

        # Store in Redis
        key = f"credentials:{credential_id}"
        if ttl:
            await self._redis.setex(key, ttl, encrypted.decode())
        else:
            await self._redis.set(key, encrypted.decode())

        logger.info("Credentials stored", credential_id=credential_id)

    async def get_credentials(self, credential_id: str) -> dict[str, str] | None:
        """Retrieve decrypted credentials.

        Args:
            credential_id: Unique identifier for the credentials

        Returns:
            Decrypted credentials or None if not found
        """
        if not self._fernet or not self._redis:
            raise RuntimeError("Credential manager not initialized")

        key = f"credentials:{credential_id}"
        encrypted = await self._redis.get(key)

        if not encrypted:
            return None

        # Decrypt credentials
        decrypted = self._fernet.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())

    async def delete_credentials(self, credential_id: str) -> bool:
        """Delete stored credentials.

        Args:
            credential_id: Unique identifier for the credentials

        Returns:
            True if deleted, False if not found
        """
        if not self._redis:
            raise RuntimeError("Credential manager not initialized")

        key = f"credentials:{credential_id}"
        result = await self._redis.delete(key)
        return result > 0

    async def rotate_credentials(
        self,
        credential_id: str,
        new_credentials: dict[str, str],
    ) -> None:
        """Rotate credentials atomically.

        Args:
            credential_id: Unique identifier for the credentials
            new_credentials: New credential values
        """
        # Store new credentials with temporary ID
        temp_id = f"{credential_id}:new"
        await self.store_credentials(temp_id, new_credentials)

        # Atomically swap
        await self._redis.rename(f"credentials:{temp_id}", f"credentials:{credential_id}")

        logger.info("Credentials rotated", credential_id=credential_id)
```

### 6. Create `/services/integration-service/src/aswa_integrations/services/integration_manager.py`
```python
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.models.integration import (
    IntegrationDB,
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationStatus,
    IntegrationType,
    Base,
)
from aswa_integrations.services.credential_manager import CredentialManager
from aswa_integrations.connectors.base import BaseConnector
from aswa_integrations.connectors.jira import JiraConnector
from aswa_integrations.connectors.webhook import WebhookConnector

logger = structlog.get_logger()


class IntegrationManager:
    """Manages integration lifecycle."""

    def __init__(self):
        self.settings = get_settings()
        self.credential_manager = CredentialManager()
        self._engine = None
        self._session_factory = None
        self._connectors: dict[IntegrationType, type[BaseConnector]] = {
            IntegrationType.JIRA: JiraConnector,
            IntegrationType.WEBHOOK: WebhookConnector,
        }

    async def initialize(self) -> None:
        """Initialize the integration manager."""
        # Create database engine
        self._engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
        )

        # Create tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Initialize credential manager
        await self.credential_manager.initialize()

        logger.info("Integration manager initialized")

    async def close(self) -> None:
        """Close connections."""
        await self.credential_manager.close()
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Integration manager not initialized")
        return self._session_factory()

    async def create_integration(
        self,
        tenant_id: str,
        data: IntegrationCreate,
    ) -> IntegrationResponse:
        """Create a new integration.

        Args:
            tenant_id: Tenant identifier
            data: Integration creation data

        Returns:
            Created integration
        """
        integration_id = str(uuid.uuid4())
        credential_id = None

        # Store credentials if provided
        if data.credentials:
            credential_id = f"{tenant_id}:{integration_id}"
            await self.credential_manager.store_credentials(
                credential_id,
                data.credentials,
            )

        # Create database record
        integration = IntegrationDB(
            id=integration_id,
            tenant_id=tenant_id,
            name=data.name,
            type=data.type,
            status=IntegrationStatus.PENDING,
            config=data.config,
            credentials_id=credential_id,
        )

        async with self._get_session() as session:
            session.add(integration)
            await session.commit()
            await session.refresh(integration)

        logger.info(
            "Integration created",
            integration_id=integration_id,
            type=data.type,
            tenant_id=tenant_id,
        )

        # Test connection
        await self._test_connection(integration)

        return IntegrationResponse.model_validate(integration)

    async def get_integration(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> IntegrationResponse | None:
        """Get an integration by ID.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            Integration or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if integration:
                return IntegrationResponse.model_validate(integration)
            return None

    async def list_integrations(
        self,
        tenant_id: str,
        integration_type: IntegrationType | None = None,
        status: IntegrationStatus | None = None,
    ) -> list[IntegrationResponse]:
        """List integrations for a tenant.

        Args:
            tenant_id: Tenant identifier
            integration_type: Optional type filter
            status: Optional status filter

        Returns:
            List of integrations
        """
        async with self._get_session() as session:
            query = select(IntegrationDB).where(
                IntegrationDB.tenant_id == tenant_id
            )

            if integration_type:
                query = query.where(IntegrationDB.type == integration_type)
            if status:
                query = query.where(IntegrationDB.status == status)

            result = await session.execute(query)
            integrations = result.scalars().all()

            return [
                IntegrationResponse.model_validate(i)
                for i in integrations
            ]

    async def update_integration(
        self,
        tenant_id: str,
        integration_id: str,
        data: IntegrationUpdate,
    ) -> IntegrationResponse | None:
        """Update an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier
            data: Update data

        Returns:
            Updated integration or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return None

            # Update fields
            if data.name is not None:
                integration.name = data.name
            if data.config is not None:
                integration.config = data.config
            if data.is_enabled is not None:
                integration.is_enabled = data.is_enabled

            # Update credentials if provided
            if data.credentials and integration.credentials_id:
                await self.credential_manager.rotate_credentials(
                    integration.credentials_id,
                    data.credentials,
                )

            integration.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(integration)

            logger.info(
                "Integration updated",
                integration_id=integration_id,
            )

            return IntegrationResponse.model_validate(integration)

    async def delete_integration(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> bool:
        """Delete an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return False

            # Delete credentials
            if integration.credentials_id:
                await self.credential_manager.delete_credentials(
                    integration.credentials_id
                )

            # Delete integration
            await session.execute(
                delete(IntegrationDB).where(IntegrationDB.id == integration_id)
            )
            await session.commit()

            logger.info(
                "Integration deleted",
                integration_id=integration_id,
            )

            return True

    async def _test_connection(self, integration: IntegrationDB) -> None:
        """Test integration connection and update status.

        Args:
            integration: Integration to test
        """
        connector_class = self._connectors.get(integration.type)
        if not connector_class:
            return

        credentials = None
        if integration.credentials_id:
            credentials = await self.credential_manager.get_credentials(
                integration.credentials_id
            )

        connector = connector_class(
            config=integration.config,
            credentials=credentials,
        )

        try:
            await connector.test_connection()
            new_status = IntegrationStatus.ACTIVE
            error = None
        except Exception as e:
            new_status = IntegrationStatus.ERROR
            error = str(e)
            logger.error(
                "Integration connection test failed",
                integration_id=str(integration.id),
                error=error,
            )

        # Update status
        async with self._get_session() as session:
            await session.execute(
                update(IntegrationDB)
                .where(IntegrationDB.id == integration.id)
                .values(
                    status=new_status,
                    last_health_check=datetime.utcnow(),
                    last_error=error,
                )
            )
            await session.commit()

    async def get_connector(
        self,
        tenant_id: str,
        integration_id: str,
    ) -> BaseConnector | None:
        """Get a configured connector for an integration.

        Args:
            tenant_id: Tenant identifier
            integration_id: Integration identifier

        Returns:
            Configured connector or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(IntegrationDB).where(
                    IntegrationDB.id == integration_id,
                    IntegrationDB.tenant_id == tenant_id,
                    IntegrationDB.is_enabled == True,
                )
            )
            integration = result.scalar_one_or_none()

            if not integration:
                return None

            connector_class = self._connectors.get(integration.type)
            if not connector_class:
                return None

            credentials = None
            if integration.credentials_id:
                credentials = await self.credential_manager.get_credentials(
                    integration.credentials_id
                )

            return connector_class(
                config=integration.config,
                credentials=credentials,
            )
```

### 7. Create `/services/integration-service/src/aswa_integrations/connectors/base.py`
```python
from abc import ABC, abstractmethod
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger()


class BaseConnector(ABC):
    """Base class for integration connectors."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        """Initialize connector.

        Args:
            config: Connector configuration
            credentials: Optional credentials
        """
        self.config = config
        self.credentials = credentials or {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Establish connection."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection.

        Returns:
            True if connection is successful

        Raises:
            Exception if connection fails
        """
        pass

    @abstractmethod
    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute an action.

        Args:
            action: Action to execute
            payload: Action payload

        Returns:
            Action result
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response
        """
        if not self._client:
            await self.connect()

        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
```

### 8. Create `/services/integration-service/src/aswa_integrations/connectors/jira.py`
```python
from typing import Any
import structlog

from aswa_integrations.connectors.base import BaseConnector

logger = structlog.get_logger()


class JiraConnector(BaseConnector):
    """Jira integration connector."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        super().__init__(config, credentials)
        self.base_url = config.get("base_url", "").rstrip("/")
        self.project_key = config.get("project_key")

    def _get_auth(self) -> tuple[str, str] | None:
        """Get authentication tuple."""
        email = self.credentials.get("email")
        api_token = self.credentials.get("api_token")
        if email and api_token:
            return (email, api_token)
        return None

    async def test_connection(self) -> bool:
        """Test connection to Jira.

        Returns:
            True if connection successful

        Raises:
            Exception if connection fails
        """
        url = f"{self.base_url}/rest/api/3/myself"
        auth = self._get_auth()

        response = await self._request("GET", url, auth=auth)
        data = response.json()

        logger.info(
            "Jira connection test successful",
            account_id=data.get("accountId"),
        )

        return True

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a Jira action.

        Args:
            action: Action type (create_issue, update_issue, etc.)
            payload: Action payload

        Returns:
            Action result
        """
        actions = {
            "create_issue": self._create_issue,
            "update_issue": self._update_issue,
            "get_issue": self._get_issue,
            "add_comment": self._add_comment,
            "transition_issue": self._transition_issue,
            "search": self._search_issues,
        }

        handler = actions.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")

        return await handler(payload)

    async def _create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a Jira issue.

        Args:
            payload: Issue data

        Returns:
            Created issue data
        """
        url = f"{self.base_url}/rest/api/3/issue"
        auth = self._get_auth()

        issue_data = {
            "fields": {
                "project": {"key": payload.get("project_key", self.project_key)},
                "summary": payload["summary"],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": payload.get("description", "")}
                            ],
                        }
                    ],
                },
                "issuetype": {"name": payload.get("issue_type", "Task")},
            }
        }

        # Add optional fields
        if payload.get("priority"):
            issue_data["fields"]["priority"] = {"name": payload["priority"]}
        if payload.get("labels"):
            issue_data["fields"]["labels"] = payload["labels"]
        if payload.get("assignee"):
            issue_data["fields"]["assignee"] = {"accountId": payload["assignee"]}

        response = await self._request(
            "POST",
            url,
            auth=auth,
            json=issue_data,
        )

        result = response.json()
        logger.info("Jira issue created", issue_key=result.get("key"))

        return result

    async def _update_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a Jira issue.

        Args:
            payload: Update data with issue_key

        Returns:
            Update result
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        auth = self._get_auth()

        update_data = {"fields": {}}

        if payload.get("summary"):
            update_data["fields"]["summary"] = payload["summary"]
        if payload.get("description"):
            update_data["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": payload["description"]}],
                    }
                ],
            }
        if payload.get("labels"):
            update_data["fields"]["labels"] = payload["labels"]

        await self._request("PUT", url, auth=auth, json=update_data)

        logger.info("Jira issue updated", issue_key=issue_key)

        return {"key": issue_key, "updated": True}

    async def _get_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Get a Jira issue.

        Args:
            payload: Contains issue_key

        Returns:
            Issue data
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        auth = self._get_auth()

        response = await self._request("GET", url, auth=auth)
        return response.json()

    async def _add_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Add a comment to an issue.

        Args:
            payload: Contains issue_key and comment

        Returns:
            Comment data
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        auth = self._get_auth()

        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": payload["comment"]}],
                    }
                ],
            }
        }

        response = await self._request("POST", url, auth=auth, json=comment_data)

        logger.info("Jira comment added", issue_key=issue_key)

        return response.json()

    async def _transition_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Transition an issue to a new status.

        Args:
            payload: Contains issue_key and transition_id

        Returns:
            Transition result
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        auth = self._get_auth()

        transition_data = {"transition": {"id": payload["transition_id"]}}

        await self._request("POST", url, auth=auth, json=transition_data)

        logger.info(
            "Jira issue transitioned",
            issue_key=issue_key,
            transition_id=payload["transition_id"],
        )

        return {"key": issue_key, "transitioned": True}

    async def _search_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Search for issues using JQL.

        Args:
            payload: Contains jql query

        Returns:
            Search results
        """
        url = f"{self.base_url}/rest/api/3/search"
        auth = self._get_auth()

        params = {
            "jql": payload.get("jql", f"project = {self.project_key}"),
            "maxResults": payload.get("max_results", 50),
            "startAt": payload.get("start_at", 0),
        }

        response = await self._request("GET", url, auth=auth, params=params)
        return response.json()
```

### 9. Create `/services/integration-service/src/aswa_integrations/connectors/webhook.py`
```python
from typing import Any
import hashlib
import hmac
import json
import structlog

from aswa_integrations.connectors.base import BaseConnector

logger = structlog.get_logger()


class WebhookConnector(BaseConnector):
    """Generic webhook connector."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        super().__init__(config, credentials)
        self.url = config.get("url", "")
        self.method = config.get("method", "POST").upper()
        self.headers = config.get("headers", {})
        self.signing_secret = credentials.get("signing_secret") if credentials else None

    async def test_connection(self) -> bool:
        """Test webhook endpoint.

        Returns:
            True if endpoint is reachable

        Raises:
            Exception if endpoint is not reachable
        """
        # Send a test ping
        test_payload = {"type": "test", "message": "ASWA webhook test"}

        headers = self._build_headers(test_payload)
        response = await self._request(
            self.method,
            self.url,
            headers=headers,
            json=test_payload,
        )

        logger.info(
            "Webhook connection test successful",
            url=self.url,
            status=response.status_code,
        )

        return True

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a webhook action.

        Args:
            action: Action type (send)
            payload: Webhook payload

        Returns:
            Webhook response
        """
        if action != "send":
            raise ValueError(f"Unknown action: {action}")

        return await self._send_webhook(payload)

    async def _send_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a webhook request.

        Args:
            payload: Request payload

        Returns:
            Response data
        """
        headers = self._build_headers(payload)

        response = await self._request(
            self.method,
            self.url,
            headers=headers,
            json=payload,
        )

        logger.info(
            "Webhook sent",
            url=self.url,
            status=response.status_code,
        )

        # Try to parse JSON response
        try:
            return response.json()
        except Exception:
            return {"status": response.status_code, "body": response.text}

    def _build_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """Build request headers with optional signing.

        Args:
            payload: Request payload for signing

        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ASWA-Integration/1.0",
            **self.headers,
        }

        # Add signature if signing secret is configured
        if self.signing_secret:
            payload_bytes = json.dumps(payload, sort_keys=True).encode()
            signature = hmac.new(
                self.signing_secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-ASWA-Signature"] = f"sha256={signature}"

        return headers
```

### 10. Create `/services/integration-service/src/aswa_integrations/connectors/__init__.py`
```python
from .base import BaseConnector
from .jira import JiraConnector
from .webhook import WebhookConnector

__all__ = ["BaseConnector", "JiraConnector", "WebhookConnector"]
```

### 11. Create `/services/integration-service/src/aswa_integrations/api/routes.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
import structlog

from aswa_integrations.models.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationType,
    IntegrationStatus,
)
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.api.dependencies import get_integration_manager, get_tenant_id

logger = structlog.get_logger()
router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Create a new integration."""
    return await manager.create_integration(tenant_id, data)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
    type: IntegrationType | None = None,
    status: IntegrationStatus | None = None,
) -> list[IntegrationResponse]:
    """List all integrations for a tenant."""
    return await manager.list_integrations(tenant_id, type, status)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Get an integration by ID."""
    integration = await manager.get_integration(tenant_id, integration_id)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return integration


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    data: IntegrationUpdate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Update an integration."""
    integration = await manager.update_integration(tenant_id, integration_id, data)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> None:
    """Delete an integration."""
    deleted = await manager.delete_integration(tenant_id, integration_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> dict:
    """Test an integration connection."""
    connector = await manager.get_connector(tenant_id, integration_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or disabled",
        )

    try:
        async with connector:
            await connector.test_connection()
        return {"status": "success", "message": "Connection test passed"}
    except Exception as e:
        logger.error("Integration test failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection test failed: {str(e)}",
        )


@router.post("/{integration_id}/execute")
async def execute_integration_action(
    integration_id: str,
    action: str,
    payload: dict,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> dict:
    """Execute an action on an integration."""
    connector = await manager.get_connector(tenant_id, integration_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or disabled",
        )

    try:
        async with connector:
            result = await connector.execute(action, payload)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Integration action failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Action failed: {str(e)}",
        )
```

### 12. Create `/services/integration-service/src/aswa_integrations/api/dependencies.py`
```python
from fastapi import Request, HTTPException, status
from aswa_integrations.services.integration_manager import IntegrationManager

_integration_manager: IntegrationManager | None = None


def set_integration_manager(manager: IntegrationManager) -> None:
    """Set the global integration manager instance."""
    global _integration_manager
    _integration_manager = manager


def get_integration_manager() -> IntegrationManager:
    """Get the integration manager dependency."""
    if not _integration_manager:
        raise RuntimeError("Integration manager not initialized")
    return _integration_manager


def get_tenant_id(request: Request) -> str:
    """Extract tenant ID from request headers."""
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return tenant_id
```

### 13. Create `/services/integration-service/src/aswa_integrations/main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.api.routes import router
from aswa_integrations.api.dependencies import set_integration_manager
from aswa_integrations.services.integration_manager import IntegrationManager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Initialize integration manager
    manager = IntegrationManager()
    await manager.initialize()
    set_integration_manager(manager)

    logger.info(
        "Integration service started",
        environment=settings.environment,
    )

    yield

    # Cleanup
    await manager.close()
    logger.info("Integration service stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Integration Service",
        description="Manages external integrations for ASWA",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.service_name}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aswa_integrations.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
```

## Test Requirements

### Create `/services/integration-service/tests/conftest.py`
```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    redis.rename = AsyncMock()
    redis.close = AsyncMock()
    return redis


@pytest.fixture
def mock_credentials():
    """Sample credentials for testing."""
    return {
        "email": "test@example.com",
        "api_token": "test-token",
    }


@pytest.fixture
def mock_jira_config():
    """Sample Jira configuration."""
    return {
        "base_url": "https://test.atlassian.net",
        "project_key": "TEST",
    }
```

### Create `/services/integration-service/tests/test_integration_manager.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.models.integration import IntegrationCreate, IntegrationType


class TestIntegrationManager:
    @pytest.fixture
    def manager(self):
        """Create an integration manager instance."""
        return IntegrationManager()

    @pytest.mark.asyncio
    async def test_create_integration(self, manager):
        """Test integration creation."""
        with patch.object(manager, '_get_session') as mock_session, \
             patch.object(manager.credential_manager, 'store_credentials', new_callable=AsyncMock), \
             patch.object(manager, '_test_connection', new_callable=AsyncMock):

            session = AsyncMock()
            session.add = MagicMock()
            session.commit = AsyncMock()
            session.refresh = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock()

            data = IntegrationCreate(
                name="Test Integration",
                type=IntegrationType.JIRA,
                config={"base_url": "https://test.atlassian.net"},
                credentials={"email": "test@example.com", "api_token": "token"},
            )

            # This would require full database setup for proper testing
            # For unit testing, we verify the method calls


class TestJiraConnector:
    @pytest.mark.asyncio
    async def test_test_connection(self, mock_jira_config, mock_credentials):
        """Test Jira connection testing."""
        from aswa_integrations.connectors.jira import JiraConnector

        connector = JiraConnector(mock_jira_config, mock_credentials)

        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"accountId": "123"}
            mock_request.return_value = mock_response

            result = await connector.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_create_issue(self, mock_jira_config, mock_credentials):
        """Test Jira issue creation."""
        from aswa_integrations.connectors.jira import JiraConnector

        connector = JiraConnector(mock_jira_config, mock_credentials)

        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"key": "TEST-123", "id": "10001"}
            mock_request.return_value = mock_response

            result = await connector._create_issue({
                "summary": "Test Issue",
                "description": "Test description",
            })

            assert result["key"] == "TEST-123"


class TestWebhookConnector:
    @pytest.mark.asyncio
    async def test_send_webhook(self):
        """Test webhook sending."""
        from aswa_integrations.connectors.webhook import WebhookConnector

        config = {
            "url": "https://example.com/webhook",
            "method": "POST",
        }
        connector = WebhookConnector(config)

        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"received": True}
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            result = await connector._send_webhook({"event": "test"})
            assert result["received"] is True

    def test_build_headers_with_signature(self):
        """Test header building with signature."""
        from aswa_integrations.connectors.webhook import WebhookConnector

        config = {"url": "https://example.com/webhook"}
        credentials = {"signing_secret": "test-secret"}
        connector = WebhookConnector(config, credentials)

        headers = connector._build_headers({"test": "data"})

        assert "X-ASWA-Signature" in headers
        assert headers["X-ASWA-Signature"].startswith("sha256=")
```

## Verification

1. Install dependencies: `cd /services/integration-service && pip install -e ".[dev]"`
2. Run tests: `pytest tests/ -v`
3. Start service: `python -m aswa_integrations.main`
4. Test health endpoint: `curl http://localhost:8004/health`
