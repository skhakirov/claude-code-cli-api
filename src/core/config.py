"""
Configuration settings for Claude Code CLI API.

Source: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings

# Source: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


class Settings(BaseSettings):
    """
    API Configuration.

    Sources:
    - PermissionMode: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
    - Model names: https://docs.anthropic.com/en/docs/about-claude/models
    """
    # API
    api_keys: list[str] = Field(default_factory=list)
    api_title: str = "Claude Code CLI API"
    api_version: str = "1.0.0"

    # Claude
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    default_max_turns: int = 20
    default_timeout: int = 300
    default_permission_mode: PermissionMode = "acceptEdits"

    # Paths
    allowed_directories: list[str] = Field(default_factory=lambda: ["/workspace"])
    default_working_directory: str = "/workspace"

    # Session cache
    session_cache_maxsize: int = 1000
    session_cache_ttl: int = 3600
    session_persistence_path: str = ""  # Path for file-based session persistence (empty = disabled)

    # Request validation
    max_request_body_size: int = 150_000  # Max request body size in bytes (150KB)

    # Retry configuration
    retry_max_attempts: int = 3
    retry_min_wait: float = 1.0  # seconds
    retry_max_wait: float = 10.0  # seconds
    retry_multiplier: float = 2.0  # exponential backoff multiplier
    retry_jitter_max: float = 1.0  # maximum random jitter in seconds (prevents thundering herd)

    # Response limits
    max_response_size: int = 10 * 1024 * 1024  # 10 MB default

    # Rate limiting
    rate_limit_requests_per_second: float = 10.0
    rate_limit_burst_size: int = 20

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_timeout: float = 30.0

    # Shutdown
    shutdown_timeout: float = 30.0  # Graceful shutdown timeout in seconds
    generator_cleanup_timeout: float = 5.0  # Timeout for SDK generator cleanup
    message_stall_timeout: float = 60.0  # Timeout for detecting stalled message processing

    # Logging
    log_level: str = "INFO"

    # Alerting
    alert_webhook_url: str = ""  # Webhook URL for critical alerts (empty = disabled)
    alert_webhook_timeout: float = 5.0  # Timeout for webhook requests

    model_config = {
        "env_prefix": "CLAUDE_API_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
