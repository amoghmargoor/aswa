"""Test fixtures for insight engine."""

import asyncio
from collections.abc import Generator
from typing import Any, Type
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from aswa_insight.llm.client import LLMClient


TEST_TENANT_ID = UUID("12345678-1234-1234-1234-123456789abc")
TEST_USER_ID = UUID("87654321-4321-4321-4321-cba987654321")
TEST_DOCUMENT_ID = UUID("abcdef12-3456-7890-abcd-ef1234567890")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, Any] = {}
        self.calls: list[dict[str, Any]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Mock initialize."""
        self._initialized = True

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Mock complete."""
        self.calls.append({
            "method": "complete",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return self._responses.get("complete", "Mock response")

    async def complete_structured(
        self,
        messages: list[dict],
        response_model: Type,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> Any:
        """Mock structured completion."""
        self.calls.append({
            "method": "complete_structured",
            "messages": messages,
            "response_model": response_model.__name__,
            "max_retries": max_retries,
        })

        # Return mock response based on model
        if "Entity" in response_model.__name__:
            return self._create_entity_response(response_model)
        elif "Risk" in response_model.__name__:
            return self._create_risk_response(response_model)
        elif "Opportunity" in response_model.__name__:
            return self._create_opportunity_response(response_model)
        elif "Pattern" in response_model.__name__:
            return self._create_pattern_response(response_model)

        return response_model()

    async def count_tokens(self, text: str) -> int:
        """Mock token counting."""
        return len(text) // 4

    async def close(self) -> None:
        """Mock close."""
        self._initialized = False

    def _create_entity_response(self, model: type) -> Any:
        """Create mock entity response."""
        from aswa_insight.services.extraction_service import ExtractedEntity

        class EntityResponse(BaseModel):
            entities: list[ExtractedEntity]

        return EntityResponse(entities=[
            ExtractedEntity(
                name="Acme Corp",
                entity_type="organization",
                description="Technology company",
                confidence=0.9,
                mentions=["Acme Corp is a technology company"],
            )
        ])

    def _create_risk_response(self, model: type) -> Any:
        """Create mock risk response."""
        from aswa_insight.services.extraction_service import ExtractedRisk

        class RiskResponse(BaseModel):
            risks: list[ExtractedRisk]

        return RiskResponse(risks=[
            ExtractedRisk(
                title="Security Risk",
                description="Potential data breach vulnerability",
                category="security",
                severity="high",
                likelihood="possible",
                mitigation="Implement MFA",
                confidence=0.85,
                evidence=["Outdated authentication system"],
            )
        ])

    def _create_opportunity_response(self, model: type) -> Any:
        """Create mock opportunity response."""
        from aswa_insight.services.extraction_service import ExtractedOpportunity

        class OpportunityResponse(BaseModel):
            opportunities: list[ExtractedOpportunity]

        return OpportunityResponse(opportunities=[
            ExtractedOpportunity(
                title="Market Expansion",
                description="Expand into APAC region",
                category="growth",
                impact="high",
                effort="medium",
                confidence=0.75,
                evidence=["Growing demand in Asia"],
            )
        ])

    def _create_pattern_response(self, model: type) -> Any:
        """Create mock pattern response."""
        from aswa_insight.services.extraction_service import ExtractedPattern

        class PatternResponse(BaseModel):
            patterns: list[ExtractedPattern]

        return PatternResponse(patterns=[
            ExtractedPattern(
                title="Quarterly Growth Trend",
                description="Consistent 10% growth each quarter",
                pattern_type="trend",
                frequency="quarterly",
                confidence=0.88,
                evidence=["Q1: 10%, Q2: 11%, Q3: 10%"],
            )
        ])

    async def health_check(self) -> bool:
        """Mock health check."""
        return True

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return "mock-model"

    def set_response(self, key: str, value: Any) -> None:
        """Set mock response for a key."""
        self._responses[key] = value


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock):
    """Create mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return factory


@pytest.fixture
def tenant_headers() -> dict[str, str]:
    """Create tenant context headers."""
    return {
        "x-tenant-id": str(TEST_TENANT_ID),
        "x-user-id": str(TEST_USER_ID),
        "x-roles": "user,admin",
    }


@pytest.fixture
def test_client(mock_llm_client: MockLLMClient, mock_session_factory) -> TestClient:
    """Create test client with mocked dependencies."""
    from aswa_insight.main import app

    # Override app state
    app.state.llm_client = mock_llm_client
    app.state.session_factory = mock_session_factory

    client = TestClient(app, raise_server_exceptions=False)
    return client
