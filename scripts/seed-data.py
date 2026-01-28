#!/usr/bin/env python3
"""Seed development database with test data."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import random
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://aswa:aswa@localhost:5432/aswa"
)


async def seed_database():
    """Seed the database with test data."""
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get dev tenant
        result = await session.execute(
            "SELECT id FROM users.tenants WHERE slug = 'dev'"
        )
        tenant_row = result.fetchone()
        if not tenant_row:
            print("Dev tenant not found. Run migrations first.")
            return

        tenant_id = tenant_row[0]
        print(f"Seeding data for tenant: {tenant_id}")

        # Create test users
        users = [
            ("alice@aswa.local", "Alice Smith", "analyst"),
            ("bob@aswa.local", "Bob Johnson", "user"),
            ("carol@aswa.local", "Carol Williams", "admin"),
        ]

        for email, name, role in users:
            await session.execute(
                """
                INSERT INTO users.users (tenant_id, email, name, password_hash, role)
                VALUES (:tenant_id, :email, :name, :password_hash, :role)
                ON CONFLICT (tenant_id, email) DO NOTHING
                """,
                {
                    "tenant_id": tenant_id,
                    "email": email,
                    "name": name,
                    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Vzn7Xo5NeZ0Kq6",
                    "role": role,
                }
            )

        # Create sample documents
        document_types = ["pdf", "docx", "xlsx", "txt"]
        document_names = [
            "Q4 Financial Report",
            "Marketing Strategy 2024",
            "Technical Architecture",
            "Risk Assessment Document",
            "Compliance Audit Report",
            "Product Roadmap",
            "Customer Survey Results",
            "Operations Manual",
        ]

        document_ids = []
        for name in document_names:
            doc_id = str(uuid.uuid4())
            doc_type = random.choice(document_types)
            await session.execute(
                """
                INSERT INTO documents.documents
                (id, tenant_id, name, content_type, size_bytes, status, created_at, processed_at)
                VALUES (:id, :tenant_id, :name, :content_type, :size_bytes, :status, :created_at, :processed_at)
                ON CONFLICT DO NOTHING
                """,
                {
                    "id": doc_id,
                    "tenant_id": tenant_id,
                    "name": f"{name}.{doc_type}",
                    "content_type": f"application/{doc_type}",
                    "size_bytes": random.randint(10000, 5000000),
                    "status": "processed",
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    "processed_at": datetime.utcnow() - timedelta(days=random.randint(0, 29)),
                }
            )
            document_ids.append(doc_id)

        # Create sample insights
        insight_types = ["risk", "opportunity"]
        severities = ["low", "medium", "high", "critical"]
        categories = ["financial", "operational", "compliance", "strategic"]

        insight_titles = [
            "Budget overrun risk identified",
            "Cost reduction opportunity",
            "Compliance gap detected",
            "Market expansion opportunity",
            "Resource constraint warning",
            "Process optimization potential",
            "Security vulnerability flagged",
            "Revenue growth opportunity",
        ]

        for i, title in enumerate(insight_titles):
            await session.execute(
                """
                INSERT INTO insights.insights
                (tenant_id, document_id, type, category, title, description, severity, confidence, created_at)
                VALUES (:tenant_id, :document_id, :type, :category, :title, :description, :severity, :confidence, :created_at)
                """,
                {
                    "tenant_id": tenant_id,
                    "document_id": random.choice(document_ids),
                    "type": random.choice(insight_types),
                    "category": random.choice(categories),
                    "title": title,
                    "description": f"Detailed analysis of {title.lower()}. This insight was automatically generated based on document analysis.",
                    "severity": random.choice(severities),
                    "confidence": random.uniform(0.7, 0.99),
                    "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 14)),
                }
            )

        await session.commit()
        print("Database seeded successfully!")
        print(f"  - Created {len(users)} users")
        print(f"  - Created {len(document_names)} documents")
        print(f"  - Created {len(insight_titles)} insights")


if __name__ == "__main__":
    asyncio.run(seed_database())
