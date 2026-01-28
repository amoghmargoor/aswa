"""Test data factories for ASWA."""

import uuid
from datetime import datetime, timedelta
from typing import Any
import random

from faker import Faker

fake = Faker()


class TenantFactory:
    """Factory for creating test tenants."""

    @staticmethod
    def create(**kwargs) -> dict[str, Any]:
        """Create a tenant with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "name": kwargs.get("name", fake.company()),
            "slug": kwargs.get("slug", fake.slug()),
            "settings": kwargs.get("settings", {"features": ["all"]}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }


class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a user with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "email": kwargs.get("email", fake.email()),
            "name": kwargs.get("name", fake.name()),
            "role": kwargs.get("role", "user"),
            "settings": kwargs.get("settings", {}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }


class DocumentFactory:
    """Factory for creating test documents."""

    CONTENT_TYPES = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain",
    }

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a document with default or custom values."""
        doc_type = kwargs.get("doc_type", random.choice(list(DocumentFactory.CONTENT_TYPES.keys())))
        name = kwargs.get("name", f"{fake.catch_phrase()}.{doc_type}")

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "name": name,
            "content_type": kwargs.get("content_type", DocumentFactory.CONTENT_TYPES[doc_type]),
            "size_bytes": kwargs.get("size_bytes", random.randint(1000, 10000000)),
            "storage_path": kwargs.get("storage_path", f"documents/{uuid.uuid4()}/{name}"),
            "status": kwargs.get("status", "pending"),
            "metadata": kwargs.get("metadata", {}),
            "uploaded_by": kwargs.get("uploaded_by"),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
            "processed_at": kwargs.get("processed_at"),
        }

    @staticmethod
    def create_batch(count: int, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Create multiple documents."""
        return [DocumentFactory.create(tenant_id) for _ in range(count)]


class InsightFactory:
    """Factory for creating test insights."""

    TYPES = ["risk", "opportunity"]
    CATEGORIES = ["financial", "operational", "compliance", "strategic", "technical"]
    SEVERITIES = ["low", "medium", "high", "critical"]

    TITLES = {
        "risk": [
            "Budget overrun risk",
            "Security vulnerability detected",
            "Compliance gap identified",
            "Resource constraint warning",
            "Timeline delay risk",
        ],
        "opportunity": [
            "Cost reduction opportunity",
            "Process optimization potential",
            "Market expansion opportunity",
            "Revenue growth potential",
            "Efficiency improvement possible",
        ],
    }

    @staticmethod
    def create(
        tenant_id: str | None = None,
        document_id: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Create an insight with default or custom values."""
        insight_type = kwargs.get("type", random.choice(InsightFactory.TYPES))
        title = kwargs.get(
            "title",
            random.choice(InsightFactory.TITLES.get(insight_type, InsightFactory.TITLES["risk"]))
        )

        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "document_id": document_id or kwargs.get("document_id", str(uuid.uuid4())),
            "type": insight_type,
            "category": kwargs.get("category", random.choice(InsightFactory.CATEGORIES)),
            "title": title,
            "description": kwargs.get("description", fake.paragraph(nb_sentences=3)),
            "severity": kwargs.get("severity", random.choice(InsightFactory.SEVERITIES)),
            "confidence": kwargs.get("confidence", round(random.uniform(0.6, 0.99), 2)),
            "metadata": kwargs.get("metadata", {}),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow()),
        }

    @staticmethod
    def create_batch(
        count: int,
        tenant_id: str | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Create multiple insights."""
        return [InsightFactory.create(tenant_id, document_id) for _ in range(count)]


class QueryFactory:
    """Factory for creating test queries."""

    SAMPLE_QUERIES = [
        "What are the main risks in this document?",
        "Summarize the key findings",
        "What are the budget implications?",
        "List the action items",
        "What compliance issues were identified?",
        "What opportunities are mentioned?",
        "What is the overall assessment?",
    ]

    @staticmethod
    def create(tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create a query with default or custom values."""
        return {
            "id": kwargs.get("id", str(uuid.uuid4())),
            "tenant_id": tenant_id or kwargs.get("tenant_id", str(uuid.uuid4())),
            "user_id": kwargs.get("user_id", str(uuid.uuid4())),
            "query": kwargs.get("query", random.choice(QueryFactory.SAMPLE_QUERIES)),
            "document_ids": kwargs.get("document_ids", []),
            "response": kwargs.get("response"),
            "citations": kwargs.get("citations", []),
            "tokens_used": kwargs.get("tokens_used", random.randint(100, 2000)),
            "duration_ms": kwargs.get("duration_ms", random.randint(500, 5000)),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
        }
