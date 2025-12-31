# Claude Code CLI API Wrapper

Headless HTTP API сервис для Claude Code CLI, построенный на [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python). Позволяет интегрировать возможности Claude Code в любые приложения через REST API.

## Возможности

- **REST API** для взаимодействия с Claude Code
- **Streaming (SSE)** для real-time ответов
- **Stateless режим** - одноразовые запросы с чистым контекстом
- **Session management** - продолжение диалогов при необходимости
- **Tools support** - Claude может читать/писать файлы, выполнять команды
- **MCP servers** - подключение внешних инструментов
- **API Key authentication** - защита endpoints

## Режимы использования

### Stateless (одноразовые запросы)

Для задач парсинга, анализа данных и других операций, где **не нужна история диалога** и важен чистый контекст:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Распарси этот JSON и верни только email адреса: {\"users\": [{\"email\": \"a@test.com\"}, {\"email\": \"b@test.com\"}]}",
    "max_turns": 1
  }'
```

**Каждый запрос без `resume` создаёт новую сессию с чистым контекстом.** Claude не помнит предыдущие запросы.

Рекомендации для stateless режима:
- **Не используйте** `resume` или `continue_conversation`
- Ставьте `max_turns: 1` для простых задач (быстрее и дешевле)
- Каждый запрос полностью независим от предыдущих

### Stateful (диалоговые сессии)

Для многошаговых задач, где Claude должен помнить контекст:

```bash
# Первый запрос - создаёт сессию
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Прочитай файл config.json"}'
# Response: {"session_id": "abc-123", ...}

# Второй запрос - продолжает сессию
curl -X POST http://localhost:8000/api/v1/query \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Теперь измени порт на 8080", "resume": "abc-123"}'
```

Claude помнит весь предыдущий контекст сессии.

## Быстрый старт

### Требования

- Python 3.10+
- Claude Code CLI авторизация (см. ниже)

### Авторизация Claude Code

API использует Claude Agent SDK, который внутри вызывает Claude Code CLI. CLI должен быть авторизован.

**Вариант 1: OAuth (рекомендуется для Claude Max/Pro подписок)**

```bash
# SDK включает bundled CLI, авторизация:
~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude login

# Или через симлинк:
ln -s ~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude /usr/local/bin/claude
claude login
```

После авторизации credentials сохраняются в `~/.claude/.credentials.json`.

**Вариант 2: API Key**

Для использования с ANTHROPIC_API_KEY:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**Проверка авторизации:**

```bash
# Проверить версию CLI
~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude --version

# Тестовый запрос
echo "Hello" | ~/.local/lib/python3.10/site-packages/claude_agent_sdk/_bundled/claude -p
```

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/skhakirov/claude_code_cli_api.git
cd claude_code_cli_api

# Установка зависимостей
pip install -r requirements.txt

# Создание конфигурации
cp .env.example .env
# Отредактируйте .env файл
```

### Конфигурация (.env)

```bash
# API ключи для аутентификации клиентов (JSON array)
CLAUDE_API_API_KEYS=["your-api-key-here"]

# Модель Claude по умолчанию
CLAUDE_API_DEFAULT_MODEL=claude-sonnet-4-20250514

# Максимум итераций агента (1-100)
CLAUDE_API_DEFAULT_MAX_TURNS=20

# Таймаут выполнения в секундах (1-600)
CLAUDE_API_DEFAULT_TIMEOUT=300

# Режим разрешений: default | acceptEdits | plan | bypassPermissions
CLAUDE_API_DEFAULT_PERMISSION_MODE=acceptEdits

# Разрешённые директории для работы (JSON array)
CLAUDE_API_ALLOWED_DIRECTORIES=["/workspace","/tmp"]

# Рабочая директория по умолчанию
CLAUDE_API_DEFAULT_WORKING_DIRECTORY=/workspace

# TTL кэша сессий в секундах
CLAUDE_API_SESSION_CACHE_TTL=3600

# Уровень логирования: DEBUG | INFO | WARNING | ERROR
CLAUDE_API_LOG_LEVEL=INFO
```

### Запуск

```bash
# Development
uvicorn src.api.main:app --reload --port 8000

# Production
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

API доступен на `http://localhost:8000`

---

## API Reference

### Аутентификация

Все endpoints (кроме `/health`) требуют заголовок `X-API-Key`:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/query
```

---

### POST /api/v1/query

Выполняет запрос к Claude и возвращает полный ответ.

#### Request Body

| Поле | Тип | Обязательный | По умолчанию | Описание |
|------|-----|--------------|--------------|----------|
| `prompt` | string | **Да** | - | Текст запроса (1-100000 символов) |
| `model` | string | Нет | из конфига | Модель Claude (`claude-sonnet-4-20250514`, `claude-opus-4-20250514`) |
| `max_turns` | integer | Нет | 20 | Максимум итераций агента (1-100) |
| `timeout` | integer | Нет | 300 | Таймаут в секундах (1-600) |
| `working_directory` | string | Нет | из конфига | Рабочая директория для Claude |
| `permission_mode` | string | Нет | `acceptEdits` | Режим разрешений (см. ниже) |
| `allowed_tools` | string[] | Нет | все | Список разрешённых инструментов |
| `disallowed_tools` | string[] | Нет | [] | Список запрещённых инструментов |
| `system_prompt` | string | Нет | null | Кастомный системный промпт |
| `resume` | string | Нет | null | ID сессии для продолжения |
| `continue_conversation` | boolean | Нет | false | Продолжить последнюю сессию |
| `fork_session` | boolean | Нет | false | Создать форк при resume |
| `mcp_servers` | object | Нет | {} | Конфигурация MCP серверов |
| `include_partial_messages` | boolean | Нет | false | Включить частичные сообщения |

#### Permission Modes

| Режим | Описание |
|-------|----------|
| `default` | Запрашивает подтверждение для опасных операций |
| `acceptEdits` | Автоматически принимает редактирование файлов |
| `plan` | Только планирование, без выполнения |
| `bypassPermissions` | Пропускает все проверки разрешений |

#### Response

```json
{
  "result": "Текстовый ответ Claude",
  "session_id": "uuid-сессии",
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
  "model": "claude-sonnet-4-20250514",
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

| Поле | Тип | Описание |
|------|-----|----------|
| `result` | string | Агрегированный текстовый ответ |
| `session_id` | string | UUID сессии для продолжения диалога |
| `status` | string | `success` \| `error` \| `timeout` |
| `duration_ms` | integer | Общее время выполнения (мс) |
| `duration_api_ms` | integer | Время API вызовов (мс) |
| `is_error` | boolean | Флаг ошибки |
| `num_turns` | integer | Количество итераций агента |
| `total_cost_usd` | float | Стоимость запроса в USD |
| `usage` | object | Использование токенов |
| `model` | string | Использованная модель |
| `tool_calls` | array | Список вызовов инструментов |
| `thinking` | array | Блоки размышлений (для reasoning моделей) |
| `error` | string | Сообщение об ошибке (если есть) |

#### Примеры

**Простой запрос:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Объясни что такое recursion"}'
```

**Запрос с чтением файла:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "prompt": "Прочитай README.md и сделай краткое резюме",
    "working_directory": "/path/to/project",
    "allowed_tools": ["Read"],
    "max_turns": 3
  }'
```

**Продолжение сессии:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "prompt": "А теперь объясни подробнее",
    "resume": "previous-session-uuid"
  }'
```

---

### POST /api/v1/query/stream

Выполняет запрос с потоковой передачей ответа через Server-Sent Events (SSE).

#### Request Body

Идентичен `/api/v1/query`.

#### Response (SSE Stream)

```
event: init
data: {"type": "system", "session_id": "uuid", "tools": [...], "model": "..."}

event: text
data: {"text": "Частичный ответ...", "model": "claude-sonnet-4-20250514"}

event: tool_use
data: {"id": "toolu_xxx", "name": "Read", "input": {...}}

event: tool_result
data: {"tool_use_id": "toolu_xxx", "content": "..."}

event: thinking
data: {"thinking": "Размышления модели..."}

event: result
data: {"session_id": "uuid", "total_cost_usd": 0.007, "num_turns": 1, "is_error": false}

event: error
data: {"error": "Описание ошибки"}
```

#### SSE Event Types

| Event | Описание |
|-------|----------|
| `init` | Инициализация сессии (tools, model, session_id) |
| `text` | Текстовый чанк ответа |
| `tool_use` | Claude вызывает инструмент |
| `tool_result` | Результат выполнения инструмента |
| `thinking` | Блок размышлений |
| `result` | Финальный результат с метриками |
| `error` | Ошибка выполнения |

#### Пример

```bash
curl -N http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"prompt": "Напиши функцию сортировки"}'
```

---

### GET /api/v1/sessions

Возвращает список всех закэшированных сессий.

#### Response

```json
[
  {
    "session_id": "uuid",
    "created_at": "2025-01-01T12:00:00Z",
    "last_activity": "2025-01-01T12:05:00Z",
    "working_directory": "/workspace",
    "model": "claude-sonnet-4-20250514",
    "prompt_count": 5,
    "total_cost_usd": 0.025
  }
]
```

---

### GET /api/v1/sessions/{session_id}

Возвращает метаданные конкретной сессии.

#### Response

```json
{
  "session_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "last_activity": "2025-01-01T12:05:00Z",
  "working_directory": "/workspace",
  "model": "claude-sonnet-4-20250514",
  "prompt_count": 5,
  "total_cost_usd": 0.025
}
```

#### Errors

| Status | Описание |
|--------|----------|
| 404 | Сессия не найдена |

---

### DELETE /api/v1/sessions/{session_id}

Удаляет сессию из кэша.

#### Response

```json
{
  "status": "deleted",
  "session_id": "uuid"
}
```

---

### GET /api/v1/health

Health check endpoint. **Не требует аутентификации.**

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Доступные инструменты Claude

При работе через API, Claude имеет доступ к следующим инструментам:

| Tool | Описание |
|------|----------|
| `Read` | Чтение файлов |
| `Write` | Запись файлов |
| `Edit` | Редактирование файлов |
| `Bash` | Выполнение shell команд |
| `Glob` | Поиск файлов по паттерну |
| `Grep` | Поиск в содержимом файлов |
| `Task` | Запуск подзадач |
| `WebFetch` | Загрузка веб-страниц |
| `WebSearch` | Поиск в интернете |
| `NotebookEdit` | Редактирование Jupyter notebooks |

### Ограничение инструментов

```json
{
  "prompt": "Прочитай файл config.json",
  "allowed_tools": ["Read"],
  "disallowed_tools": ["Bash", "Write"]
}
```

---

## Интеграции

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

# Использование
result = await query_claude(
    "Напиши функцию fibonacci",
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

1. Используйте **HTTP Request** node
2. Настройте:
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

### docker-compose.yml (локальная разработка)

```yaml
services:
  claude-api:
    build: .
    container_name: claude-code-api
    restart: unless-stopped
    environment:
      - CLAUDE_API_API_KEYS=${CLAUDE_API_API_KEYS}
      - CLAUDE_API_DEFAULT_MODEL=${CLAUDE_API_DEFAULT_MODEL:-claude-sonnet-4-20250514}
      - CLAUDE_API_DEFAULT_PERMISSION_MODE=${CLAUDE_API_DEFAULT_PERMISSION_MODE:-acceptEdits}
      - CLAUDE_API_LOG_LEVEL=${CLAUDE_API_LOG_LEVEL:-INFO}
    volumes:
      - ./workspace:/workspace:rw
    ports:
      - "8000:8000"
```

### docker-compose.yml (production с Traefik)

```yaml
services:
  claude-api:
    build: .
    container_name: claude-code-api
    restart: unless-stopped
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CLAUDE_API_API_KEYS=${CLAUDE_API_API_KEYS}
      - CLAUDE_API_DEFAULT_MODEL=${CLAUDE_API_DEFAULT_MODEL:-claude-sonnet-4-20250514}
      - CLAUDE_API_DEFAULT_PERMISSION_MODE=${CLAUDE_API_DEFAULT_PERMISSION_MODE:-acceptEdits}
      - CLAUDE_API_LOG_LEVEL=${CLAUDE_API_LOG_LEVEL:-INFO}
    volumes:
      - ./workspace:/workspace:rw
    ports:
      - "8000:8000"
    networks:
      - traefik
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.claude-api.rule=Host(`claude-api.yourdomain.com`)"
      - "traefik.http.routers.claude-api.entrypoints=websecure"
      - "traefik.http.routers.claude-api.tls.certresolver=letsencrypt"
      - "traefik.http.services.claude-api.loadbalancer.server.port=8000"
      - "traefik.http.middlewares.claude-ratelimit.ratelimit.average=20"
      - "traefik.http.middlewares.claude-ratelimit.ratelimit.burst=10"
      - "traefik.http.routers.claude-api.middlewares=claude-ratelimit"

networks:
  traefik:
    external: true
```

### Запуск

```bash
# Сборка и запуск
docker-compose up -d

# Логи
docker-compose logs -f claude-api
```

### Важно: Claude авторизация в Docker

Claude CLI использует авторизацию из `~/.claude/.credentials.json`. Для Docker:

1. **OAuth (рекомендуется)**: Авторизуйтесь на хост-машине через `claude login`, затем примонтируйте credentials:
   ```yaml
   volumes:
     - ~/.claude:/home/appuser/.claude:ro
   ```

2. **API Key**: Установите `ANTHROPIC_API_KEY` в environment

---

## Коды ошибок

| HTTP Code | Описание |
|-----------|----------|
| 200 | Успешный запрос |
| 400 | Невалидный запрос или path traversal |
| 401 | Отсутствует или неверный API ключ |
| 403 | Доступ к директории запрещён |
| 404 | Сессия не найдена |
| 422 | Ошибка валидации параметров |
| 500 | Внутренняя ошибка сервера или Claude SDK |
| 502 | Ошибка соединения с Claude |
| 503 | Claude CLI недоступен |

---

## Безопасность

### Path Traversal Protection

API защищает от path traversal атак:
- Все пути нормализуются
- Проверяется принадлежность к `allowed_directories`
- Паттерны вроде `../` блокируются

### API Key Authentication

- Все endpoints (кроме `/health`) требуют валидный API ключ
- Ключи передаются через заголовок `X-API-Key`
- Поддержка нескольких ключей для ротации

### Рекомендации

1. Используйте HTTPS в production (через reverse proxy)
2. Ограничьте `allowed_directories` минимально необходимыми путями
3. Используйте `permission_mode: acceptEdits` вместо `bypassPermissions`
4. Регулярно ротируйте API ключи
5. Настройте rate limiting на уровне reverse proxy

---

## Тестирование

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=src --cov-report=html

# Только unit тесты
pytest tests/unit/ -v

# Только интеграционные
pytest tests/integration/ -v
```

---

## Переменные окружения

| Переменная | Обязательная | По умолчанию | Описание |
|------------|--------------|--------------|----------|
| `CLAUDE_API_API_KEYS` | Да | - | JSON array API ключей |
| `CLAUDE_API_DEFAULT_MODEL` | Нет | `claude-sonnet-4-20250514` | Модель по умолчанию |
| `CLAUDE_API_DEFAULT_MAX_TURNS` | Нет | `20` | Макс. итераций |
| `CLAUDE_API_DEFAULT_TIMEOUT` | Нет | `300` | Таймаут (сек) |
| `CLAUDE_API_DEFAULT_PERMISSION_MODE` | Нет | `acceptEdits` | Режим разрешений |
| `CLAUDE_API_ALLOWED_DIRECTORIES` | Нет | `["/workspace"]` | Разрешённые пути |
| `CLAUDE_API_DEFAULT_WORKING_DIRECTORY` | Нет | `/workspace` | Рабочая директория |
| `CLAUDE_API_SESSION_CACHE_MAXSIZE` | Нет | `1000` | Макс. сессий в кэше |
| `CLAUDE_API_SESSION_CACHE_TTL` | Нет | `3600` | TTL кэша (сек) |
| `CLAUDE_API_LOG_LEVEL` | Нет | `INFO` | Уровень логов |

---

## Лицензия

MIT

## Ссылки

- [Claude Agent SDK (Python)](https://github.com/anthropics/claude-agent-sdk-python)
- [SDK Documentation](https://platform.claude.com/docs/en/agent-sdk/python)
- [Claude Code CLI](https://code.claude.com/docs/en/cli-reference)
- [Headless Mode](https://code.claude.com/docs/en/headless)
