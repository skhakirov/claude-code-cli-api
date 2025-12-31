# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-31

### Added

- **Core API Endpoints**
  - `POST /api/v1/query` - Execute Claude Code CLI queries
  - `POST /api/v1/query/stream` - Server-Sent Events streaming
  - `GET /api/v1/sessions` - List all sessions
  - `GET /api/v1/sessions/{id}` - Get session details
  - `DELETE /api/v1/sessions/{id}` - Delete session
  - `GET /api/v1/health` - Health check endpoint

- **Security Features**
  - API key authentication via `X-API-Key` header
  - Path traversal protection with directory allowlisting
  - Request body size limits
  - Prompt sanitization

- **Reliability Features**
  - Circuit breaker pattern for SDK calls
  - Retry logic with exponential backoff
  - Graceful shutdown with task tracking
  - Session cache with TTL and persistence

- **Observability**
  - Structured logging with structlog
  - Request/response logging middleware
  - Alert webhooks for critical errors
  - X-Request-ID header support

- **Configuration**
  - Environment-based configuration via pydantic-settings
  - Multiple API keys support
  - Configurable timeouts and limits
  - MCP server configuration

- **Docker Support**
  - Production-ready Dockerfile with non-root user
  - Docker Compose with Traefik integration

### Documentation

- Comprehensive README with API reference
- Integration examples (Python, JavaScript, n8n, Telegram)
- Security recommendations
- Docker deployment guide

[1.0.0]: https://github.com/skhakirov/claude-code-cli-api/releases/tag/v1.0.0
