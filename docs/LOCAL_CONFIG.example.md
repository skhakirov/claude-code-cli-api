# Claude Code API — Local Configuration

> **Note for AI agents**: This document describes how to connect to the Claude Code API from other services on this VPS.

## Endpoints

| Access Type | URL | Use Case |
|-------------|-----|----------|
| External (HTTPS) | `https://claude-api.YOUR_DOMAIN/api/v1/` | Public access, external clients |
| Internal (Docker) | `http://claude-code-api:8000/api/v1/` | Services in `vps_app-network` |
| Localhost | `http://localhost:8002/api/v1/` | Scripts running on VPS host |

## Authentication

All API requests require the `X-API-Key` header:

```
X-API-Key: YOUR_API_KEY
```

The API key is defined in `.env` file (`CLAUDE_API_API_KEYS`).

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check (no auth required) |
| `/api/v1/query` | POST | Execute Claude query |
| `/api/v1/query/stream` | POST | Execute with SSE streaming |
| `/api/v1/sessions/{id}` | GET | Get session info |

## Request Examples

### Python (internal Docker network)

```python
import httpx

response = httpx.post(
    "http://claude-code-api:8000/api/v1/query",
    headers={"X-API-Key": "YOUR_API_KEY"},
    json={
        "prompt": "List files in current directory",
        "working_directory": "/workspace"
    },
    timeout=300.0
)
print(response.json())
```

### curl (from VPS host)

```bash
curl -X POST http://localhost:8002/api/v1/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, Claude!", "working_directory": "/workspace"}'
```

### curl (external HTTPS)

```bash
curl -X POST https://claude-api.YOUR_DOMAIN/api/v1/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "working_directory": "/workspace"}'
```

### Streaming (SSE)

```bash
curl -N -X POST http://localhost:8002/api/v1/query/stream \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a poem"}'
```

## Docker Network Configuration

The API container runs in the `vps_app-network`. To connect other services:

```yaml
# In your service's docker-compose.yml
services:
  your-service:
    # ... your config
    networks:
      - vps_app-network

networks:
  vps_app-network:
    external: true
```

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | Yes | The prompt/instruction for Claude |
| `working_directory` | string | No | Working directory (default: /workspace) |
| `model` | string | No | Model to use (default from config) |
| `max_turns` | int | No | Max agent iterations (1-100) |
| `permission_mode` | string | No | One of: default, acceptEdits, plan, bypassPermissions |
| `system_prompt` | string | No | Custom system prompt |
| `allowed_tools` | list | No | Whitelist of tools |
| `disallowed_tools` | list | No | Blacklist of tools |
| `session_id` | string | No | Resume existing session |

## Response Format

```json
{
  "session_id": "abc123",
  "result": "Claude's response text",
  "is_error": false,
  "duration_ms": 1234,
  "num_turns": 1,
  "total_cost_usd": 0.01
}
```

## Allowed Directories

Claude can only access files in directories specified in `CLAUDE_API_ALLOWED_DIRECTORIES`:
- `/workspace` — isolated working directory
- `/home/lancer/projects` — your project files (if configured)

## Troubleshooting

### Check API health
```bash
curl http://localhost:8002/api/v1/health
```

### View container logs
```bash
docker logs -f claude-code-api
```

### Restart container
```bash
cd ~/projects/claude-api
docker compose -f docker-compose.prod.yml restart
```
