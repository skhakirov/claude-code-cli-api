# Claude Code CLI API Wrapper

[![Tests](https://github.com/skhakirov/claude-code-cli-api/actions/workflows/test.yml/badge.svg)](https://github.com/skhakirov/claude-code-cli-api/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/skhakirov/claude-code-cli-api)](https://github.com/skhakirov/claude-code-cli-api/releases)

Headless HTTP API service for Claude Code CLI, built on [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python). Enables integration of Claude Code capabilities into any application via REST API.

## Features

- **REST API** for interacting with Claude Code
- **Streaming (SSE)** for real-time responses
- **Stateless mode** - one-shot requests with clean context
- **Session management** - continue conversations when needed
- **Tools support** - Claude can read/write files, execute commands
- **MCP servers** - connect external tools
- **API Key authentication** - secure endpoints
- **Circuit breaker** - automatic failure handling
- **Retry logic** - exponential backoff for transient errors

## Usage Modes

### Stateless (One-Shot Requests)

For parsing, data analysis, and other operations where **conversation history is not needed** and clean context is important:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Parse this JSON and return only email addresses: {\"users\": [{\"email\": \"a@test.com\"}, {\"email\": \"b@test.com\"}]}",
    "max_turns": 1
  }'
```

**Each request without `resume` creates a new session with clean context.** Claude does not remember previous requests.

Recommendations for stateless mode:
- **Do not use** `resume` or `continue_conversation`
- Set `max_turns: 1` for simple tasks (faster and cheaper)
- Each request is completely independent from previous ones

### Stateful (Dialog Sessions)

For multi-step tasks where Claude needs to remember context:

```bash
# First request - creates session
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Read file config.json"}'
# Response: {"session_id": "abc-123", ...}

# Second request - continues session
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Now change the port to 8080", "resume": "abc-123"}'
```

Claude remembers all previous session context.

## Quick Start

### Requirements

- Python 3.10+
- Claude Code CLI authorization (see below)

### Claude Code Authorization

The API uses Claude Agent SDK, which internally calls Claude Code CLI. The CLI must be authorized.

**Option 1: OAuth (recommended for Claude Max/Pro subscriptions)**

```bash
# SDK includes bundled CLI, authorization:
~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude login

# Or via symlink:
ln -s ~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude /usr/local/bin/claude
claude login
```

After authorization, credentials are saved to `~/.claude/.credentials.json`.

**Option 2: API Key**

For use with ANTHROPIC_API_KEY:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**Verify authorization:**

```bash
# Check CLI version
~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude --version

# Test request
echo "Hello" | ~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude -p
```

### Installation

```bash
# Clone repository
git clone https://github.com/skhakirov/claude-code-cli-api.git
cd claude-code-cli-api

# Install dependencies
pip install -r requirements.txt

# Create configuration
cp .env.example .env
# Edit .env file
```

### Configuration (.env)

```bash
# API keys for client authentication (JSON array)
CLAUDE_API_API_KEYS=["your-api-key-here"]

# Default Claude model
CLAUDE_API_DEFAULT_MODEL=claude-sonnet-4-5-20250929

# Maximum agent iterations (1-100)
CLAUDE_API_DEFAULT_MAX_TURNS=20

# Execution timeout in seconds (1-600)
CLAUDE_API_DEFAULT_TIMEOUT=300

# Permission mode: default | acceptEdits | plan | bypassPermissions
CLAUDE_API_DEFAULT_PERMISSION_MODE=acceptEdits

# Allowed working directories (JSON array)
CLAUDE_API_ALLOWED_DIRECTORIES=["/workspace","/tmp"]

# Default working directory
CLAUDE_API_DEFAULT_WORKING_DIRECTORY=/workspace

# Session cache TTL in seconds
CLAUDE_API_SESSION_CACHE_TTL=3600

# Log level: DEBUG | INFO | WARNING | ERROR
CLAUDE_API_LOG_LEVEL=INFO
```

### Running

```bash
# Development
uvicorn src.api.main:app --reload --port 8000

# Production
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`

---

## API Reference

### Authentication

All endpoints (except `/health`) require `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/query
```

---

### POST /api/v1/query

Executes a query to Claude and returns the complete response.

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | **Yes** | - | Query text (1-100000 characters) |
| `model` | string | No | from config | Claude model (`claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101`) |
| `max_turns` | integer | No | 20 | Maximum agent iterations (1-100) |
| `timeout` | integer | No | 300 | Timeout in seconds (1-600) |
| `working_directory` | string | No | from config | Working directory for Claude |
| `permission_mode` | string | No | `acceptEdits` | Permission mode (see below) |
| `allowed_tools` | string[] | No | all | List of allowed tools |
| `disallowed_tools` | string[] | No | [] | List of disallowed tools |
| `system_prompt` | string | No | null | Custom system prompt |
| `resume` | string | No | null | Session ID to continue |
| `continue_conversation` | boolean | No | false | Continue last session |
| `fork_session` | boolean | No | false | Create fork on resume |
| `mcp_servers` | object | No | {} | MCP servers configuration |
| `include_partial_messages` | boolean | No | false | Include partial messages |

#### Permission Modes

| Mode | Description |
|------|-------------|
| `default` | Asks for confirmation on dangerous operations |
| `acceptEdits` | Automatically accepts file edits |
| `plan` | Planning only, no execution |
| `bypassPermissions` | Skips all permission checks |

#### Response

```json
{
  "result": "Claude's text response",
  "session_id": "session-uuid",
  "status": "success",
  "duration_ms": 4737,
  "duration_api_ms": 4023,
  "is_error": false,
  "num_turns": 1,
  "total_cost_usd": 0.0063,
  "usage": {
    "input_tokens": 100,
    "output_tokens": 50
  },
  "model": "claude-sonnet-4-5-20250929",
  "tool_calls": [
    {
      "id": "toolu_xxx",
      "name": "Read",
      "input": {"file_path": "/path/to/file"},
      "output": null
    }
  ],
  "thinking": [],
  "error": null
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `result` | string | Aggregated text response |
| `session_id` | string | Session UUID for continuing dialog |
| `status` | string | `success` \| `error` \| `timeout` |
| `duration_ms` | integer | Total execution time (ms) |
| `duration_api_ms` | integer | API call time (ms) |
| `is_error` | boolean | Error flag |
| `num_turns` | integer | Number of agent iterations |
| `total_cost_usd` | float | Request cost in USD |
| `usage` | object | Token usage |
| `model` | string | Model used |
| `tool_calls` | array | List of tool calls |
| `thinking` | array | Thinking blocks (for reasoning models) |
| `error` | string | Error message (if any) |

#### Examples

**Simple request:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Explain what recursion is"}'
```

**Request with file reading:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "prompt": "Read README.md and create a brief summary",
    "working_directory": "/path/to/project",
    "allowed_tools": ["Read"],
    "max_turns": 3
  }'
```

**Continue session:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "prompt": "Now explain in more detail",
    "resume": "previous-session-uuid"
  }'
```

---

### POST /api/v1/query/stream

Executes query with streaming response via Server-Sent Events (SSE).

#### Request Body

Identical to `/api/v1/query`.

#### Response (SSE Stream)

```
event: init
data: {"type": "system", "session_id": "uuid", "tools": [...], "model": "..."}

event: text
data: {"text": "Partial response...", "model": "claude-sonnet-4-5-20250929"}

event: tool_use
data: {"id": "toolu_xxx", "name": "Read", "input": {...}}

event: tool_result
data: {"tool_use_id": "toolu_xxx", "content": "..."}

event: thinking
data: {"thinking": "Model reasoning..."}

event: result
data: {"session_id": "uuid", "total_cost_usd": 0.007, "num_turns": 1, "is_error": false}

event: error
data: {"error": "Error description"}
```

#### SSE Event Types

| Event | Description |
|-------|-------------|
| `init` | Session initialization (tools, model, session_id) |
| `text` | Text chunk of response |
| `tool_use` | Claude calls a tool |
| `tool_result` | Tool execution result |
| `thinking` | Thinking block |
| `result` | Final result with metrics |
| `error` | Execution error |

#### Example

```bash
curl -N http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Write a sorting function"}'
```

---

### GET /api/v1/sessions

Returns list of all cached sessions.

#### Response

```json
[
  {
    "session_id": "uuid",
    "created_at": "2025-01-01T12:00:00Z",
    "last_activity": "2025-01-01T12:05:00Z",
    "working_directory": "/workspace",
    "model": "claude-sonnet-4-5-20250929",
    "prompt_count": 5,
    "total_cost_usd": 0.025
  }
]
```

---

### GET /api/v1/sessions/{session_id}

Returns metadata for specific session.

#### Response

```json
{
  "session_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "last_activity": "2025-01-01T12:05:00Z",
  "working_directory": "/workspace",
  "model": "claude-sonnet-4-5-20250929",
  "prompt_count": 5,
  "total_cost_usd": 0.025
}
```

#### Errors

| Status | Description |
|--------|-------------|
| 404 | Session not found |

---

### DELETE /api/v1/sessions/{session_id}

Deletes session from cache.

#### Response

```json
{
  "status": "deleted",
  "session_id": "uuid"
}
```

---

### GET /api/v1/health

Basic health check endpoint. **Does not require authentication.**

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

### GET /api/v1/health/ready

Detailed readiness check endpoint. **Does not require authentication.** Use for Kubernetes/Docker readiness probes.

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "cache": {
    "status": "healthy",
    "sessions_count": 5,
    "max_size": 1000
  },
  "sdk": {
    "status": "healthy",
    "available": true,
    "version": "0.1.18"
  },
  "memory": {
    "rss_mb": 128.5,
    "peak_mb": 256.0,
    "vms_mb": 512.0,
    "status": "healthy"
  },
  "disk": {
    "free_gb": 50.0,
    "total_gb": 100.0,
    "used_percent": 50.0,
    "status": "healthy"
  },
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0,
    "is_available": true
  },
  "active_tasks": 2
}
```

#### Status Values

| Component | Status Values |
|-----------|---------------|
| Overall | `healthy`, `degraded`, `unhealthy` |
| Cache | `healthy`, `full` |
| SDK | `healthy`, `unavailable` |
| Memory | `healthy`, `high`, `critical` |
| Disk | `healthy`, `warning`, `critical` |
| Circuit Breaker | `closed`, `open`, `half_open` |

---

### GET /api/v1/metrics

Application metrics endpoint. **Does not require authentication.** Use for monitoring dashboards.

#### Response

```json
{
  "requests_total": 1000,
  "requests_error": 10,
  "tokens_input": 50000,
  "tokens_output": 25000,
  "latency_histogram": {
    "p50": 1500,
    "p95": 3000,
    "p99": 5000
  },
  "endpoints": {
    "/api/v1/query": {
      "count": 800,
      "errors": 5
    }
  },
  "status_codes": {
    "200": 980,
    "401": 10,
    "500": 5
  }
}
```

---

## Available Claude Tools

When working through the API, Claude has access to the following tools:

| Tool | Description |
|------|-------------|
| `Read` | Read files |
| `Write` | Write files |
| `Edit` | Edit files |
| `Bash` | Execute shell commands |
| `Glob` | Search files by pattern |
| `Grep` | Search in file contents |
| `Task` | Run subtasks |
| `WebFetch` | Fetch web pages |
| `WebSearch` | Search the internet |
| `NotebookEdit` | Edit Jupyter notebooks |

### Limiting Tools

```json
{
  "prompt": "Read file config.json",
  "allowed_tools": ["Read"],
  "disallowed_tools": ["Bash", "Write"]
}
```

---

## Integrations

### Python

```python
import httpx

API_URL = "http://localhost:8000/api/v1"
API_KEY = "your-api-key"

async def query_claude(prompt: str, **kwargs) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/query",
            headers={"X-API-Key": API_KEY},
            json={"prompt": prompt, **kwargs},
            timeout=300
        )
        return response.json()

# Usage
result = await query_claude(
    "Write a fibonacci function",
    max_turns=5,
    allowed_tools=["Write"]
)
print(result["result"])
```

### Python (Streaming)

```python
import json
import httpx

async def stream_claude(prompt: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{API_URL}/query/stream",
            headers={"X-API-Key": API_KEY},
            json={"prompt": prompt},
            timeout=300
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    yield data
```

### JavaScript/TypeScript

```typescript
const API_URL = "http://localhost:8000/api/v1";
const API_KEY = "your-api-key";

async function queryClaude(prompt: string, options = {}): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: JSON.stringify({ prompt, ...options }),
  });
  return response.json();
}

// Streaming
async function* streamClaude(prompt: string) {
  const response = await fetch(`${API_URL}/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: JSON.stringify({ prompt }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

### n8n Integration

1. Use **HTTP Request** node
2. Configure:
   - Method: `POST`
   - URL: `http://your-server:8000/api/v1/query`
   - Authentication: Header Auth
   - Header Name: `X-API-Key`
   - Header Value: `your-api-key`
3. Body (JSON):
   ```json
   {
     "prompt": "{{ $json.userMessage }}",
     "max_turns": 10
   }
   ```

### Telegram Bot

```python
from aiogram import Bot, Dispatcher, types
import httpx

API_URL = "http://localhost:8000/api/v1"
API_KEY = "your-api-key"

@dp.message()
async def handle_message(message: types.Message):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/query",
            headers={"X-API-Key": API_KEY},
            json={
                "prompt": message.text,
                "max_turns": 5
            },
            timeout=120
        )
        result = response.json()
        await message.answer(result["result"])
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /workspace
RUN useradd -r -u 1000 -d /app appuser && chown -R appuser:appuser /app /workspace
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml (local development)

```yaml
services:
  claude-api:
    build: .
    container_name: claude-code-api
    restart: unless-stopped
    environment:
      - CLAUDE_API_API_KEYS=${CLAUDE_API_API_KEYS}
      - CLAUDE_API_DEFAULT_MODEL=${CLAUDE_API_DEFAULT_MODEL:-claude-sonnet-4-5-20250929}
      - CLAUDE_API_DEFAULT_PERMISSION_MODE=${CLAUDE_API_DEFAULT_PERMISSION_MODE:-acceptEdits}
      - CLAUDE_API_LOG_LEVEL=${CLAUDE_API_LOG_LEVEL:-INFO}
    volumes:
      - ./workspace:/workspace:rw
    ports:
      - "8000:8000"
```

### docker-compose.yml (production with nginx)

```yaml
services:
  claude-api:
    build: .
    container_name: claude-code-api
    restart: unless-stopped
    user: "1000:1000"
    environment:
      - CLAUDE_API_API_KEYS=${CLAUDE_API_API_KEYS}
      - CLAUDE_API_DEFAULT_MODEL=${CLAUDE_API_DEFAULT_MODEL:-claude-sonnet-4-5-20250929}
      - CLAUDE_API_DEFAULT_PERMISSION_MODE=${CLAUDE_API_DEFAULT_PERMISSION_MODE:-acceptEdits}
      - CLAUDE_API_ALLOWED_DIRECTORIES=${CLAUDE_API_ALLOWED_DIRECTORIES:-["/workspace"]}
      - CLAUDE_API_LOG_LEVEL=${CLAUDE_API_LOG_LEVEL:-INFO}
      - HOME=/home/appuser
    volumes:
      - ./workspace:/workspace:rw
      - ./appuser-home:/home/appuser:rw
    ports:
      - "127.0.0.1:8002:8000"  # Expose only to localhost (nginx handles HTTPS)
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  app-network:
    external: true
```

Configure nginx as reverse proxy with SSL termination (example `/etc/nginx/sites-available/claude-api`):

```nginx
server {
    listen 443 ssl http2;
    server_name claude-api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Rate limiting (optional)
    limit_req zone=claude_api burst=20 nodelay;
}
```

### Running

```bash
# Build and run
docker-compose up -d

# Logs
docker-compose logs -f claude-api
```

### Important: Claude Authorization in Docker

Claude CLI uses authorization from `~/.claude/.credentials.json`. For Docker:

1. **OAuth (recommended)**: Authorize on host machine via `claude login`, then mount credentials:
   ```yaml
   volumes:
     - ~/.claude:/home/appuser/.claude:ro
   ```

2. **API Key**: Set `ANTHROPIC_API_KEY` in environment

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Successful request |
| 400 | Invalid request or path traversal |
| 401 | Missing or invalid API key |
| 403 | Directory access denied |
| 404 | Session not found |
| 413 | Request body too large |
| 415 | Unsupported media type |
| 422 | Parameter validation error |
| 500 | Internal server error or Claude SDK error |
| 502 | Claude connection error |
| 503 | Claude CLI unavailable or circuit breaker open |
| 504 | Execution timeout |

---

## Security

### Path Traversal Protection

The API protects against path traversal attacks:
- All paths are normalized
- Checked for belonging to `allowed_directories`
- Patterns like `../` are blocked

### API Key Authentication

- All endpoints (except `/health`) require a valid API key
- Keys are passed via `X-API-Key` header
- Multiple keys supported for rotation

### Recommendations

1. Use HTTPS in production (via reverse proxy)
2. Limit `allowed_directories` to minimum necessary paths
3. Use `permission_mode: acceptEdits` instead of `bypassPermissions`
4. Regularly rotate API keys
5. Configure rate limiting at reverse proxy level

---

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests only
pytest tests/e2e/ -v
```

---

## Environment Variables

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLAUDE_API_API_KEYS` | Yes | - | JSON array of API keys |
| `ANTHROPIC_API_KEY` | No* | - | Anthropic API key (alternative to OAuth) |
| `CLAUDE_API_DEFAULT_MODEL` | No | `claude-sonnet-4-5-20250929` | Default model |
| `CLAUDE_API_DEFAULT_MAX_TURNS` | No | `20` | Max iterations (1-100) |
| `CLAUDE_API_DEFAULT_TIMEOUT` | No | `300` | Timeout in seconds (1-600) |
| `CLAUDE_API_DEFAULT_PERMISSION_MODE` | No | `acceptEdits` | Permission mode |
| `CLAUDE_API_ALLOWED_DIRECTORIES` | No | `["/workspace"]` | Allowed paths (JSON array) |
| `CLAUDE_API_DEFAULT_WORKING_DIRECTORY` | No | `/workspace` | Working directory |
| `CLAUDE_API_LOG_LEVEL` | No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

### Session Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_SESSION_CACHE_MAXSIZE` | `1000` | Max sessions in cache |
| `CLAUDE_API_SESSION_CACHE_TTL` | `3600` | Cache TTL in seconds |
| `CLAUDE_API_SESSION_PERSISTENCE_PATH` | `` | Path for file-based persistence (empty = disabled) |

### Request Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_MAX_REQUEST_BODY_SIZE` | `150000` | Max request body size in bytes (150KB) |
| `CLAUDE_API_MAX_RESPONSE_SIZE` | `10485760` | Max response size in bytes (10MB) |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_RATE_LIMIT_REQUESTS_PER_SECOND` | `10.0` | Requests per second limit |
| `CLAUDE_API_RATE_LIMIT_BURST_SIZE` | `20` | Burst size for rate limiting |

### Retry Logic

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `CLAUDE_API_RETRY_MIN_WAIT` | `1.0` | Min wait between retries (sec) |
| `CLAUDE_API_RETRY_MAX_WAIT` | `10.0` | Max wait between retries (sec) |
| `CLAUDE_API_RETRY_MULTIPLIER` | `2.0` | Exponential backoff multiplier |
| `CLAUDE_API_RETRY_JITTER_MAX` | `1.0` | Max random jitter (sec) |

### Circuit Breaker

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Failures before circuit opens |
| `CLAUDE_API_CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `2` | Successes to close circuit |
| `CLAUDE_API_CIRCUIT_BREAKER_TIMEOUT` | `30.0` | Time in open state (sec) |

### Graceful Shutdown

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_SHUTDOWN_TIMEOUT` | `30.0` | Graceful shutdown timeout (sec) |
| `CLAUDE_API_GENERATOR_CLEANUP_TIMEOUT` | `5.0` | SDK generator cleanup timeout (sec) |
| `CLAUDE_API_MESSAGE_STALL_TIMEOUT` | `60.0` | Stalled message detection timeout (sec) |

### Alerting (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_ALERT_WEBHOOK_URL` | `` | Webhook URL for critical alerts (empty = disabled) |
| `CLAUDE_API_ALERT_WEBHOOK_TIMEOUT` | `5.0` | Webhook request timeout (sec) |

---

## License

MIT

## Links

- [Claude Agent SDK (Python)](https://github.com/anthropics/claude-agent-sdk-python)
- [SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/python)
- [Claude Code CLI](https://code.claude.com/docs/en/cli-reference)
- [Headless Mode](https://code.claude.com/docs/en/headless)
