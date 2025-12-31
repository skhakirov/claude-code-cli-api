"""
TDD: Configuration tests.
Status: RED (must fail before implementation)
"""


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

    def test_settings_retry_jitter_max(self):
        """Settings should have retry_jitter_max for thundering herd prevention."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.retry_jitter_max == 1.0
        assert isinstance(settings.retry_jitter_max, float)

    def test_settings_generator_cleanup_timeout(self):
        """Settings should have generator_cleanup_timeout."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.generator_cleanup_timeout == 5.0
        assert isinstance(settings.generator_cleanup_timeout, float)

    def test_settings_message_stall_timeout(self):
        """Settings should have message_stall_timeout for stuck detection."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.message_stall_timeout == 60.0
        assert isinstance(settings.message_stall_timeout, float)

    def test_settings_custom_robustness_values(self):
        """Settings should accept custom robustness values."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test",
            retry_jitter_max=2.5,
            generator_cleanup_timeout=10.0,
            message_stall_timeout=120.0
        )
        assert settings.retry_jitter_max == 2.5
        assert settings.generator_cleanup_timeout == 10.0
        assert settings.message_stall_timeout == 120.0

    def test_settings_max_request_body_size(self):
        """Settings should have max_request_body_size for validation middleware."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.max_request_body_size == 150_000
        assert isinstance(settings.max_request_body_size, int)

    def test_settings_session_persistence_path_default_empty(self):
        """Session persistence path should default to empty (disabled)."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.session_persistence_path == ""

    def test_settings_custom_persistence_path(self):
        """Settings should accept custom persistence path."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test",
            session_persistence_path="/var/data/sessions.json"
        )
        assert settings.session_persistence_path == "/var/data/sessions.json"

    def test_settings_alert_webhook_url_default_empty(self):
        """Alert webhook URL should default to empty (disabled)."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.alert_webhook_url == ""

    def test_settings_alert_webhook_timeout_default(self):
        """Alert webhook timeout should have default value."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test"
        )
        assert settings.alert_webhook_timeout == 5.0

    def test_settings_custom_alert_webhook(self):
        """Settings should accept custom alert webhook config."""
        from src.core.config import Settings

        settings = Settings(
            api_keys=["test"],
            anthropic_api_key="sk-ant-test",
            alert_webhook_url="https://alerts.example.com/webhook",
            alert_webhook_timeout=10.0
        )
        assert settings.alert_webhook_url == "https://alerts.example.com/webhook"
        assert settings.alert_webhook_timeout == 10.0
