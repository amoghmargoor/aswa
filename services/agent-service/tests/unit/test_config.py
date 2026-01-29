"""Tests for configuration management."""

import pytest
from aswa_agents.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()

        assert settings.service_name == "agent-service"
        assert settings.port == 8090
        assert settings.environment == "development"
        assert not settings.is_production

    def test_production_check(self):
        """Test production environment detection."""
        settings = Settings(environment="production")
        assert settings.is_production

    def test_database_url_parsing(self):
        """Test database URL is valid."""
        settings = Settings()
        assert "postgresql" in str(settings.database_url)

    def test_redis_url_parsing(self):
        """Test Redis URL is valid."""
        settings = Settings()
        assert "redis" in str(settings.redis_url)

    def test_llm_provider_default(self):
        """Test default LLM provider."""
        settings = Settings()
        assert settings.llm_provider == "anthropic"

    def test_high_risk_actions_default(self):
        """Test default high-risk actions list."""
        settings = Settings()
        assert "send_email" in settings.high_risk_actions
        assert "create_ticket" in settings.high_risk_actions

    def test_get_settings_cached(self):
        """Test settings are cached."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
