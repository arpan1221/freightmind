# Story 1.1: Scaffold Backend Project with uv, FastAPI, and Docker

Status: done

## Story

As a developer,
I want a runnable FastAPI backend with uv dependency management, a Docker image, and environment variable configuration,
so that I have a deployable foundation on which all agents and routes are built.

## Acceptance Criteria

1. **Given** the developer clones the repo and has Docker installed, **When** they run `docker-compose up backend`, **Then** the FastAPI server starts on port 8000 with no errors AND `GET /docs` returns the auto-generated OpenAPI Swagger UI AND no API keys or secrets appear in any committed file (NFR10)

2. **Given** a `.env` file is present with `OPENROUTER_API_KEY` set, **When** the backend starts, **Then** `core/config.py` loads the value via Pydantic `BaseSettings` without crashing

3. **Given** `BYPASS_CACHE=true` is set in the environment, **When** the backend starts, **Then** `core/config.py` exposes `bypass_cache=True` accessible to future `ModelClient` (FR44)

## Tasks / Subtasks

- [x] Task 1: Initialise backend project with uv (AC: 1, 2, 3)
  - [x] Run `uv init backend --python 3.12` from repo root
  - [x] `cd backend` and run `uv add "fastapi[standard]" uvicorn pymupdf openai sqlalchemy python-multipart pandas`
  - [x] Run `uv add --dev ruff mypy`
  - [x] Verify `pyproject.toml` and `uv.lock` are generated

- [x] Task 2: Create FastAPI app skeleton (AC: 1)
  - [x] Create `backend/app/__init__.py` (empty)
  - [x] Create `backend/app/main.py` — FastAPI app instance, CORS middleware (wildcard `*`), HTTPException override, lifespan hook (empty for now), include routers placeholder
  - [x] Create `backend/app/core/__init__.py` (empty)
  - [x] Create `backend/app/core/config.py` — Pydantic `BaseSettings` with `openrouter_api_key`, `bypass_cache`, `database_url`, `cache_dir`
  - [x] Create `backend/app/api/__init__.py` (empty)
  - [x] Create `backend/app/api/routes/__init__.py` (empty)
  - [x] Create `backend/app/api/routes/system.py` — stub `GET /api/health` returning `{"status": "ok"}` (full impl in Story 1.4)
  - [x] Create `backend/app/schemas/__init__.py` (empty)
  - [x] Create `backend/app/schemas/common.py` — `ErrorResponse` Pydantic model

- [x] Task 3: Create directory scaffolding (AC: 1)
  - [x] Create `backend/app/agents/__init__.py`, `backend/app/agents/analytics/__init__.py`, `backend/app/agents/extraction/__init__.py`
  - [x] Create `backend/app/services/__init__.py`
  - [x] Create `backend/app/models/__init__.py`
  - [x] Create `backend/app/prompts/` directory with `.gitkeep`
  - [x] Create `backend/data/` directory (SCMS CSV will be placed here)
  - [x] Create `backend/cache/.gitkeep`

- [x] Task 4: Create environment config files (AC: 2, 3)
  - [x] Create `backend/.env.example` — documents `OPENROUTER_API_KEY`, `BYPASS_CACHE`, `DATABASE_URL`, `CACHE_DIR`
  - [x] Add `backend/.env` to `.gitignore`
  - [x] Create root `.env.example` for docker-compose

- [x] Task 5: Create backend Dockerfile (AC: 1)
  - [x] Create `backend/Dockerfile` using the canonical uv pattern (see Dev Notes)

- [x] Task 6: Create docker-compose.yml at repo root (AC: 1)
  - [x] Wire backend service with port 8000, env_file, and cache volume mount
  - [x] Add frontend service placeholder (build: ./frontend) so compose file is complete for Epic 1
  - [x] Set `NEXT_PUBLIC_BACKEND_URL=http://backend:8000` on frontend service

- [x] Task 7: Verify runnable state (AC: 1)
  - [x] `docker-compose up backend` starts without errors
  - [x] `GET http://localhost:8000/docs` returns Swagger UI
  - [x] `GET http://localhost:8000/api/health` returns `{"status": "ok"}`

## Dev Notes

### Exact uv Initialisation Commands

Run from the **repo root** (`freightmind/`):
```bash
uv init backend --python 3.12
cd backend
uv add "fastapi[standard]" uvicorn pymupdf "openai>=1.0" sqlalchemy "python-multipart>=0.0.9" "pandas>=2.0"
uv add --dev ruff mypy
```

**Why `openai` SDK?** OpenRouter uses an OpenAI-compatible API — set `base_url="https://openrouter.ai/api/v1"` and `api_key=OPENROUTER_API_KEY`. No separate HTTP client needed.

### Canonical Backend Dockerfile

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app/ ./app/
COPY data/ ./data/
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Critical:** `COPY --from=ghcr.io/astral-sh/uv:latest` is the correct pattern for uv in Docker. Do NOT use `pip install -r requirements.txt` — there is no `requirements.txt` in a uv project.

### Canonical docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: ./backend/.env
    volumes:
      - ./backend/cache:/app/cache

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_BACKEND_URL=http://backend:8000
    depends_on:
      - backend
```

### app/main.py — Required Patterns

Three things MUST be in `main.py` from day one:

**1. CORS wildcard (architecture decision):**
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

**2. HTTPException override (architecture decision — overrides FastAPI default `{"detail": "..."}`)**
```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.schemas.common import ErrorResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            message=str(exc.detail),
            retry_after=None
        ).model_dump()
    )
```

**3. Lifespan hook (empty stub — Stories 1.2/1.3 will populate it):**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Stories 1.2 and 1.3 will add DB init and CSV load here
    yield

app = FastAPI(title="FreightMind API", lifespan=lifespan)
```

### core/config.py — Pydantic BaseSettings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    bypass_cache: bool = False
    database_url: str = "sqlite:///./freightmind.db"
    cache_dir: str = "./cache"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

**Note:** `pydantic-settings` is included in `fastapi[standard]` — no separate install needed.

### schemas/common.py — ErrorResponse

```python
from pydantic import BaseModel
from typing import Optional

class ErrorResponse(BaseModel):
    error: Optional[str] = None
    message: Optional[str] = None
    retry_after: Optional[int] = None
```

This is the **only** error shape used across all endpoints. Never return `{"detail": "..."}`.

### .env.example Contents

```
# Required
OPENROUTER_API_KEY=your_key_here

# Optional — defaults shown
BYPASS_CACHE=false
DATABASE_URL=sqlite:///./freightmind.db
CACHE_DIR=./cache
```

### Target Directory Structure After This Story

```
freightmind/
├── docker-compose.yml
├── .env.example
├── .gitignore
│
└── backend/
    ├── Dockerfile
    ├── pyproject.toml
    ├── uv.lock
    ├── .env.example
    │
    └── app/
        ├── __init__.py
        ├── main.py                    # FastAPI app, CORS, exception handler, lifespan stub
        ├── core/
        │   ├── __init__.py
        │   └── config.py              # Pydantic BaseSettings
        ├── models/
        │   └── __init__.py            # Empty — ORM models added in Story 1.2
        ├── schemas/
        │   ├── __init__.py
        │   └── common.py              # ErrorResponse
        ├── agents/
        │   ├── __init__.py
        │   ├── analytics/
        │   │   └── __init__.py
        │   └── extraction/
        │       └── __init__.py
        ├── services/
        │   └── __init__.py            # Empty — ModelClient added in Story 1.6
        ├── api/
        │   ├── __init__.py
        │   └── routes/
        │       ├── __init__.py
        │       └── system.py          # Stub GET /api/health
        └── prompts/
            └── .gitkeep
```

### Scope Boundary — What NOT to Implement in This Story

| Concern | Belongs To |
|---------|-----------|
| DB table creation / SQLAlchemy models | Story 1.2 |
| CSV loading | Story 1.3 |
| Full health check (DB + model reachability) | Story 1.4 |
| Prompt .txt files | Story 1.5 |
| ModelClient, cache, retry logic | Story 1.6 |
| Frontend scaffold | Story 1.7 |

The `GET /api/health` stub in this story returns `{"status": "ok"}` only — no DB check, no model ping. Story 1.4 will replace it.

### Naming Conventions (Architecture Enforced)

- Python files: `snake_case` (`model_client.py`, `analytics_planner.py`)
- Python classes: `PascalCase` (`ModelClient`, `AnalyticsPlanner`)
- Pydantic request schemas: `PascalCase` + `Request` suffix (`AnalyticsQueryRequest`)
- Pydantic response schemas: `PascalCase` + `Response` suffix (`AnalyticsQueryResponse`)
- Log via `import logging; logger = logging.getLogger(__name__)` — never `print()`
- JSON fields: `snake_case` throughout — no camelCase conversion layer

### Architecture Red Flags to Avoid

- `import openai` anywhere outside `services/model_client.py` (doesn't exist yet — just don't add it elsewhere)
- `{"data": ..., "status": "ok"}` response envelopes — direct response body only
- Hardcoded prompt strings anywhere in agent files — must live in `prompts/*.txt`

### Project Structure Notes

- This is a monorepo. `backend/` and `frontend/` are sibling directories under `freightmind/`
- The repo root holds `docker-compose.yml`, root `.env.example`, and `README.md`
- `backend/cache/` is mounted as a Docker volume to persist cache across container restarts locally
- `backend/data/` will hold the SCMS CSV — it will be committed in Story 1.3

### References

- [Source: architecture.md#Backend Initialisation] — uv commands, project structure
- [Source: architecture.md#Infrastructure & Deployment] — Docker Compose structure, backend Dockerfile
- [Source: architecture.md#Format Patterns > FastAPI Error Override] — HTTPException handler pattern
- [Source: architecture.md#Authentication & Security] — CORS wildcard decision
- [Source: architecture.md#Enforcement Guidelines] — red flags list
- [Source: epics.md#Story 1.1] — acceptance criteria

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- **Starlette 1.0.0 / FastAPI 0.135.2 HTTPException override**: Route-not-found 404s are raised as `starlette.exceptions.HTTPException`, not `fastapi.HTTPException`. Registered `@app.exception_handler(StarletteHTTPException)` (importing from `starlette.exceptions`) to catch both routing 404s and explicitly raised exceptions. FastAPI's own `HTTPException` inherits from Starlette's so this is the correct catch-all.

### Completion Notes List

- Initialized `backend/` with uv 0.8.3, Python 3.12. All production and dev deps installed; `pyproject.toml` and `uv.lock` committed.
- `app/main.py`: FastAPI app with CORS wildcard, `StarletteHTTPException` handler returning `ErrorResponse`, empty lifespan stub, and `system` router registered.
- `app/core/config.py`: Pydantic `BaseSettings` loading `OPENROUTER_API_KEY`, `BYPASS_CACHE`, `DATABASE_URL`, `CACHE_DIR` from `.env`. All AC2/AC3 fields verified by tests.
- `app/schemas/common.py`: `ErrorResponse` model — single error shape for all endpoints.
- `app/api/routes/system.py`: Stub `GET /api/health` → `{"status": "ok"}`.
- Full directory scaffold created (agents, services, models, prompts, data, cache).
- `backend/Dockerfile` uses canonical `COPY --from=ghcr.io/astral-sh/uv:latest` pattern; Docker build and `docker-compose up backend` both verified working.
- `docker-compose.yml` at repo root: backend + frontend placeholder wired correctly.
- `.gitignore` created; `backend/.env` excluded from git.
- 11 tests written covering all ACs; all pass. Ruff lint clean.

### File List

- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/Dockerfile`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/system.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/common.py`
- `backend/app/agents/__init__.py`
- `backend/app/agents/analytics/__init__.py`
- `backend/app/agents/extraction/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/prompts/.gitkeep`
- `backend/cache/.gitkeep`
- `backend/.env.example`
- `backend/tests/__init__.py`
- `backend/tests/test_story_1_1.py`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`

### Review Findings

- [x] [Review][Decision] Health route `/api` prefix baked into route path vs. mounted via `include_router(prefix="/api")` — fixed: moved `/api` to `include_router(prefix="/api")`, route is now `@router.get("/health")`.
- [x] [Review][Patch] `backend/data/` directory missing from committed files — fixed: added `backend/data/.gitkeep`. [Dockerfile:7]
- [x] [Review][Patch] `backend/.env.example` absent from diff — file exists; was absent from diff only due to diff scope. No action needed. [backend/.env.example]
- [x] [Review][Patch] `uv.lock` absent from diff — file exists; was absent from diff only due to diff scope. No action needed. [backend/uv.lock]
- [x] [Review][Patch] Unversioned `uv` image tag `:latest` — fixed: pinned to `ghcr.io/astral-sh/uv:0.8.3`. [Dockerfile:2]
- [x] [Review][Patch] `exc.detail` coerced via `str()` may produce ugly output — fixed: use `exc.detail` directly when it is already a string. [backend/app/main.py:34]
- [x] [Review][Patch] `test_bypass_cache_true_when_env_set` tests a local class replica — fixed: now instantiates real `Settings` class from `app.core.config`. [backend/tests/test_story_1_1.py:71]
- [x] [Review][Patch] `pytest-asyncio` missing from dev dependencies — already present in `pyproject.toml`; false positive. [backend/pyproject.toml]
- [x] [Review][Defer] No non-root user in Dockerfile — security hardening; belongs to deployment story (6.2). [Dockerfile] — deferred, pre-existing
- [x] [Review][Defer] `depends_on` without `condition: service_healthy` — needs healthcheck from Story 1.4 before this is actionable. [docker-compose.yml:16] — deferred, pre-existing
- [x] [Review][Defer] `settings = Settings()` at module level crashes at import if `OPENROUTER_API_KEY` missing — mitigated by startup validation when lifespan is populated in Stories 1.2/1.3. [backend/app/core/config.py:14] — deferred, pre-existing
- [x] [Review][Defer] `docker-compose env_file: ./backend/.env` fails on missing file at fresh clone — developer setup concern; mitigated once `backend/.env.example` is present. [docker-compose.yml:6] — deferred, pre-existing
- [x] [Review][Defer] No lifespan error handling — relevant when DB init and CSV load are added in Stories 1.2/1.3. [backend/app/main.py:15] — deferred, pre-existing
- [x] [Review][Defer] `os.environ.setdefault` at module level in tests mutates process env — only a concern if missing-key tests are added; current suite is unaffected. [backend/tests/test_story_1_1.py:15] — deferred, pre-existing

## Change Log

- 2026-03-30: Story 1.1 implemented — backend scaffold with uv, FastAPI, Docker, environment config, and full test suite (11 tests passing).
- 2026-03-30: Code review — 1 decision-needed, 7 patches, 6 deferred, 2 dismissed.
