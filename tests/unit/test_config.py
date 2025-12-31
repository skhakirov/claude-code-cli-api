"""
TDD: Configuration tests.
Status: RED (must fail before implementation)
"""
import pytest


class TestSettings:
    """Tests for Settings class."""

    def test_settings_loads_api_keys(self, mock_settings):
        """Settings should load API keys from env."""
        # Arrange & Act
        from src.core.config import Settings

        # Assert
        settings = Settings(
            api_keys=["key1", "key2"],
            anthropic_api_key="sk-ant-test"
        )
        assert len(settings.api_keys) == 2
        assert "key1" in settings.api_keys

    def test_settings_default_model(self):
        """Settings should have a default model."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.default_model == "claude-sonnet-4-20250514"

    def test_settings_permission_mode_validation(self):
        """PermissionMode should only accept valid values."""
        from src.core.config import Settings

        # Valid
        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test",
            default_permission_mode="bypassPermissions"
        )
        assert settings.default_permission_mode == "bypassPermissions"

    def test_settings_default_values(self):
        """Settings should have sensible defaults."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.default_max_turns == 20
        assert settings.default_timeout == 300
        assert settings.session_cache_maxsize == 1000
        assert settings.session_cache_ttl == 3600
        assert settings.log_level == "INFO"

    def test_settings_allowed_directories_default(self):
        """Settings should have default allowed directories."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert "/workspace" in settings.allowed_directories

    def test_get_settings_cached(self):
        """get_settings() should return cached instance."""
        from src.core.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
