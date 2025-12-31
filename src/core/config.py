"""
Configuration settings for Claude Code CLI API.

Source: https://platform.claude.com/docs/en/agent-sdk/python#permissionmode
"""
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

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

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_prefix": "CLAUDE_API_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
