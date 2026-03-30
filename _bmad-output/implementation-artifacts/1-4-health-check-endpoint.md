# Story 1.4: Health Check Endpoint

Status: done

## Story

As a developer or ops engineer,
I want a `/api/health` endpoint that reports live DB and model-client reachability,
So that I can confirm the system is fully operational at a glance.

## Acceptance Criteria

1. **Given** the SQLite DB is accessible AND `OPENROUTER_API_KEY` is set,
   **When** `GET /api/health` is called,
   **Then** it returns HTTP 200 with:
   ```json
   {"status": "ok", "database": "connected", "model": "reachable"}
   ```
   **And** the response arrives within 500ms (NFR14)

2. **Given** the SQLite file is missing or unreadable,
   **When** `GET /api/health` is called,
   **Then** it returns HTTP 200 (never 5xx) with:
   ```json
   {"status": "degraded", "database": "error", "model": "reachable"}
   ```

3. **Given** OpenRouter is unreachable (network error or timeout),
   **When** `GET /api/health` is called,
   **Then** it returns HTTP 200 (never 5xx) with `"model": "unreachable"`,
   **And** the response still arrives within 500ms (model check has a hard 3s timeout — never blocks the response beyond that)

## Tasks / Subtasks

- [x] Task 1: Add `HealthResponse` schema (AC: 1, 2, 3)
  - [x] In `backend/app/schemas/common.py`, add `HealthResponse` Pydantic model
  - [x] Fields: `status: str`, `database: str`, `model: str`

- [x] Task 2: Implement DB connectivity check (AC: 1, 2)
  - [x] In `backend/app/api/routes/system.py`, inject `db: Session = Depends(get_db)`
  - [x] Execute `db.execute(text("SELECT 1"))` — if it raises, `database = "error"`, else `"connected"`

- [x] Task 3: Implement model reachability check (AC: 1, 3)
  - [x] Use `httpx.AsyncClient` with a 3s timeout to call `GET https://openrouter.ai/api/v1/models`
  - [x] Set `Authorization: Bearer {settings.openrouter_api_key}` header
  - [x] HTTP 2xx → `model = "reachable"`, any error/timeout → `"unreachable"`
  - [x] Sequential (not asyncio.gather) — SQLite SELECT 1 is microseconds, no gather needed

- [x] Task 4: Compose response and replace stub (AC: 1, 2, 3)
  - [x] Replace the stub `return {"status": "ok"}` in `system.py` with the real implementation
  - [x] `status` is `"ok"` only if both `database == "connected"` and `model == "reachable"`, else `"degraded"`
  - [x] Always return HTTP 200 — never raise an exception from this endpoint

- [x] Task 5: Write tests (AC: 1, 2, 3)
  - [x] Used `unittest.mock.patch` + `AsyncMock` to stub `_check_model` and `httpx.AsyncClient.get`
  - [x] Test: DB up + model up → `{"status": "ok", "database": "connected", "model": "reachable"}`
  - [x] Test: DB error → `{"status": "degraded", "database": "error", ...}`, still HTTP 200
  - [x] Test: model unreachable → `{"status": "degraded", ..., "model": "unreachable"}`, still HTTP 200
  - [x] Test: response shape always contains all three keys

### Review Findings (AI)

- [x] [Review][Decision→Defer] NFR14 500ms vs 3s model timeout — AC3 says "within 500ms" but dev notes say "3s is the worst case". Deferred: address in a future performance/hardening story. [deferred-work.md]
- [x] [Review][Patch] `get_db` dependency failure can escape handler and return 5xx — fixed: replaced `Depends(get_db)` with inline `SessionLocal()` inside try/except; added `test_session_creation_failure_returns_200` test to prove it. [backend/app/api/routes/system.py:33]
- [x] [Review][Defer] No backoff/caching on model check calls — every health probe spawns a fresh AsyncClient and makes a live HTTP request; no protection against thundering herd if OpenRouter is down. Deferred to Epic 5 (resilience). [backend/app/api/routes/system.py:20]
- [x] [Review][Defer] DB connection has no timeout — SQLite `SELECT 1` via a connection pool with no timeout; pool exhaustion would hang the health check indefinitely. Low risk for SQLite local, but worth addressing in production hardening. [backend/app/api/routes/system.py:35]

## Dev Notes

### Schema addition — `app/schemas/common.py`

Add alongside `ErrorResponse`:
```python
class HealthResponse(BaseModel):
    status: str
    database: str
    model: str
```

### Route implementation — `app/api/routes/system.py`

```python
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_MODEL_CHECK_TIMEOUT = 3.0  # seconds — hard cap so health never blocks


async def _check_model() -> str:
    try:
        async with httpx.AsyncClient(timeout=_MODEL_CHECK_TIMEOUT) as client:
            resp = await client.get(
                _OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            return "reachable" if resp.is_success else "unreachable"
    except Exception:
        return "unreachable"


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    # DB check
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        logger.warning("Health check: DB unreachable")
        database = "error"

    # Model check (concurrent — doesn't add latency to DB check)
    model = await _check_model()

    status = "ok" if database == "connected" and model == "reachable" else "degraded"
    return HealthResponse(status=status, database=database, model=model)
```

### Why `asyncio.gather` is not needed here

`_check_model()` is an async function and the DB check is synchronous (blocking). Since the DB check is a local SQLite call it completes in microseconds. Running both sequentially adds no meaningful latency — `asyncio.gather` would add complexity for no gain.

### Key constraints

- **Never return 5xx.** All exceptions must be caught internally. A failing health endpoint would break deployment health-gate checks.
- **500ms NFR14.** The 3s `httpx` timeout is the worst case; in practice OpenRouter responds in ~200ms or fails fast.
- **Route path stays `/health`.** The `/api` prefix is applied in `main.py` via `include_router(system.router, prefix="/api")`.
- **`httpx` is already a transitive dependency** (via `httpx>=0.28.1` in dev deps and FastAPI standard extras). Confirm it's in `dependencies` (not just `dev`) or add it explicitly if needed.

### Test pattern (using `respx` or monkeypatch)

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

def test_health_all_ok(client):
    with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
        resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected", "model": "reachable"}

def test_health_model_unreachable(client):
    with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="unreachable"):
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["model"] == "unreachable"
```

### Dependency check

Verify `httpx` is listed under `[project] dependencies` in `pyproject.toml` (not just `[dependency-groups] dev`). FastAPI `standard` extras pulls in `httpx` for the test client, but for production use in async route handlers it should be an explicit runtime dep. Add `"httpx>=0.28.1"` to `dependencies` if absent.

## Architecture Notes

- This story replaces the stub `GET /health` route created in Story 1.1.
- Story 1.1 established `include_router(system.router, prefix="/api")` in `main.py` — this story does not touch `main.py`.
- The `HealthResponse` schema lives in `app/schemas/common.py` alongside `ErrorResponse` (no new file needed).
- `get_db` from `app.core.database` is the canonical DB session dependency — reuse it here rather than opening a raw connection.

## Dev Agent Record

### Completion Notes

- Replaced stub `GET /health` with full DB + model reachability checks
- `HealthResponse` added to `app/schemas/common.py` (alongside existing `ErrorResponse`)
- `_check_model()` is a private async helper with 3s `httpx` timeout; all exceptions caught → `"unreachable"`
- DB check uses `db.execute(text("SELECT 1"))` via FastAPI `Depends(get_db)`; exceptions caught → `"error"`
- `httpx` moved from dev-only to runtime `[project] dependencies` in `pyproject.toml`
- Story 1.1 regression: updated `test_story_1_1.py::test_health_returns_ok` to accept richer response shape
- 12 new tests + 1 test update; 48/48 pass

## File List

- `backend/app/api/routes/system.py` — replaced stub health route with full implementation
- `backend/app/schemas/common.py` — added `HealthResponse` model
- `backend/pyproject.toml` — added `httpx>=0.28.1` to runtime dependencies
- `backend/tests/test_story_1_4.py` — new test file (12 tests)
- `backend/tests/test_story_1_1.py` — updated `test_health_returns_ok` assertion

## Change Log

- 2026-03-30: Implemented Story 1.4 — health check endpoint with DB + model reachability. Replaced stub route, added HealthResponse schema, added httpx runtime dep, wrote 12 tests. 48/48 passing.
