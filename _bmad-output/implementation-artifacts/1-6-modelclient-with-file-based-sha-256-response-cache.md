# Story 1.6: ModelClient with File-Based SHA-256 Response Cache

Status: done

## Story

As a developer,
I want a `ModelClient` that is the sole gateway for all LLM API calls, with a file-based SHA-256 response cache and configurable bypass,
So that LLM API calls are reused during development to preserve the 50 req/day free tier quota.

## Acceptance Criteria

1. **Given** `ModelClient.call(model, messages, temperature)` is called with a payload
   **When** a cached response exists for the SHA-256 hash of `sort_keys=True` JSON serialisation of `{model, messages, temperature}` (NFR13)
   **Then** the cached response is returned within 2 seconds (NFR3)
   **And** the log entry shows `cache_hit=True`, `model_name`, `retry_count`

2. **Given** no cached response exists
   **When** `ModelClient.call()` is invoked
   **Then** the live OpenRouter API is called and the response is written to the cache file
   **And** the log entry shows `cache_hit=False`, `model_name`, and `retry_count=0`

3. **Given** `BYPASS_CACHE=true` is set
   **When** `ModelClient.call()` is invoked
   **Then** the cache is skipped entirely and a live API call is made regardless of cached state

4. **Given** any agent module imports LLM functionality
   **When** the code is inspected
   **Then** it imports `ModelClient` from `services/model_client.py` — no direct `openai` or `httpx` LLM calls exist outside `model_client.py`

## Tasks / Subtasks

- [x] Task 1: Create `backend/app/services/cache.py` — SHA-256 file cache (AC: 1, 2, 3)
  - [x] Implement `make_cache_key(model, messages, temperature) -> str` using `hashlib.sha256` + `json.dumps(sort_keys=True)`
  - [x] Implement `get_cached_response(key: str, cache_dir: str) -> dict | None` — reads `{cache_dir}/{key}.json`, returns None if missing
  - [x] Implement `write_cached_response(key: str, response: dict, cache_dir: str) -> None` — writes `{cache_dir}/{key}.json` (atomic write pattern: write to temp file, rename)
  - [x] Use `Path(cache_dir).mkdir(parents=True, exist_ok=True)` to ensure cache dir exists before read/write
  - [x] All functions are pure/synchronous (no async) — `ModelClient` controls the async boundary

- [x] Task 2: Create `backend/app/services/model_client.py` — ModelClient (AC: 1, 2, 3, 4)
  - [x] Import `openai` and configure with `base_url="https://openrouter.ai/api/v1"` and `api_key=settings.openrouter_api_key`
  - [x] Implement `async def call(self, model: str, messages: list[dict], temperature: float = 0.0) -> str` — returns the text content of the first choice
  - [x] Before any API call: if `settings.bypass_cache` is False, call `get_cached_response(key, cache_dir)` — if hit, log and return
  - [x] On cache miss: call OpenRouter API, write result to cache, log with `cache_hit=False`, `retry_count=0`
  - [x] Log using `logging.getLogger(__name__)` — INFO level with `cache_hit`, `model_name`, `retry_count` fields
  - [x] `ModelClient` accepts `cache_dir: str = settings.cache_dir` in `__init__` for test injection
  - [x] Set `timeout=httpx.Timeout(5.0)` on the `openai.AsyncOpenAI` client (NFR11)

- [x] Task 3: Write tests (AC: 1, 2, 3, 4)
  - [x] Create `backend/tests/test_story_1_6.py`
  - [x] Test: `make_cache_key` returns same hash for same inputs regardless of dict insertion order
  - [x] Test: `make_cache_key` returns different hashes for different models, messages, or temperatures
  - [x] Test: `get_cached_response` returns `None` for non-existent key
  - [x] Test: `write_cached_response` then `get_cached_response` round-trips the response dict
  - [x] Test: `ModelClient.call()` returns cached response on cache hit (mock OpenRouter — must NOT call API)
  - [x] Test: `ModelClient.call()` calls OpenRouter API on cache miss and writes to cache
  - [x] Test: `ModelClient.call()` skips cache when `BYPASS_CACHE=true` (always calls API)
  - [x] Test: No `import openai` exists outside `model_client.py` (grep `backend/app/agents/` and `backend/app/api/`)

### Review Findings

**Senior Developer Review (AI)** — 2026-03-30 | Sources: Blind Hunter + Edge Case Hunter + Acceptance Auditor

- [x] [Review][Decision] **bypass_cache=True still writes to cache after the live call** — resolved: Option A, skip both read AND write when bypassed. Fixed in `model_client.py`.
- [x] [Review][Patch] **`completion.choices[0]` crashes on empty choices list or None content** [model_client.py:59] — fixed: guard raises `ValueError` with clear message on empty choices or None content.
- [x] [Review][Patch] **Malformed cache JSON not handled — JSONDecodeError poisons the key permanently** [cache.py:23] — fixed: EAFP pattern catches `JSONDecodeError`, returns None, falls through to live API.
- [x] [Review][Patch] **`write_cached_response` failure loses the already-fetched API response** [model_client.py:61] — fixed: `OSError` caught, warning logged, `content` still returned.
- [x] [Review][Patch] **`cached["content"]` KeyError on cache file missing the content key** [model_client.py:52] — fixed: `.get("content")` with None check; falls through to live API on missing key.
- [x] [Review][Patch] **TOCTOU in `get_cached_response`: exists() check then read_text() not atomic** [cache.py:18-19] — fixed: replaced exists()+read with EAFP try/except FileNotFoundError.
- [x] [Review][Defer] **Non-JSON-serialisable values in messages raise TypeError before any API call** [cache.py:11] — deferred; caller responsibility per story spec (`messages: list[dict]` must be JSON-serialisable)
- [x] [Review][Defer] **Concurrent writes to same key share a single `.tmp` filename — Windows FileExistsError** [cache.py:34] — deferred; asyncio is single-threaded, this is a dev cache; multi-process safety out of scope
- [x] [Review][Defer] **`httpx.AsyncClient` is never closed — connection leak on shutdown** [model_client.py:28] — deferred; lifecycle management (graceful shutdown) is Epic 6 scope
- [x] [Review][Defer] **`settings.cache_dir = "./cache"` is relative — resolves against CWD at call time** [config.py] — deferred; pre-existing design in config.py, not introduced by this story
- [x] [Review][Defer] **Sensitive prompt/response data stored in plaintext on disk** [cache.py] — deferred; by design for development quota management; security hardening out of scope
- [x] [Review][Defer] **API errors propagate raw with no structured handling** [model_client.py] — deferred; explicitly Epic 5 scope (stories 5.2, 5.3, 5.5)

## Dev Notes

### Architecture Mandate: ModelClient is the ONLY LLM gateway

```python
# CORRECT — all LLM calls go through ModelClient
from app.services.model_client import ModelClient
client = ModelClient()
response = await client.call(model="meta-llama/llama-3.3-70b-instruct", messages=[...])

# WRONG — never in agent files, route files, or anywhere outside model_client.py
import openai
openai.AsyncOpenAI().chat.completions.create(...)
```

Architecture red flag: `import openai` outside of `model_client.py`. The test suite must enforce this.

### File locations (authoritative from architecture)

```
backend/app/services/
├── model_client.py     # THIS STORY — ALL OpenRouter calls go here
└── cache.py            # THIS STORY — SHA-256 file cache read/write
```

The `__init__.py` already exists in `backend/app/services/`. Do NOT create a new one.

### Cache key pattern (NFR13 — mandatory)

```python
import hashlib, json

def make_cache_key(model: str, messages: list, temperature: float) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature},
        sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()
```

`sort_keys=True` is **mandatory** — key must be deterministic regardless of dict insertion order. The hash is a hex string (64 chars). Cache files are stored as `{cache_dir}/{hash}.json`.

### `cache.py` implementation

```python
import hashlib
import json
import os
from pathlib import Path


def make_cache_key(model: str, messages: list, temperature: float) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature},
        sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached_response(key: str, cache_dir: str) -> dict | None:
    path = Path(cache_dir) / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cached_response(key: str, response: dict, cache_dir: str) -> None:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    final_path = cache_path / f"{key}.json"
    # Atomic write: write to temp, rename to final
    tmp_path = cache_path / f"{key}.json.tmp"
    tmp_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    tmp_path.rename(final_path)
```

### `model_client.py` implementation

```python
import logging
import openai
import httpx

from app.core.config import settings
from app.services.cache import make_cache_key, get_cached_response, write_cached_response

logger = logging.getLogger(__name__)


class ModelClient:
    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = cache_dir or settings.cache_dir
        self._client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.AsyncClient(timeout=httpx.Timeout(5.0)),
        )

    async def call(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
    ) -> str:
        cache_key = make_cache_key(model, messages, temperature)

        if not settings.bypass_cache:
            cached = get_cached_response(cache_key, self._cache_dir)
            if cached is not None:
                logger.info(
                    "ModelClient cache hit",
                    extra={"cache_hit": True, "model_name": model, "retry_count": 0},
                )
                return cached["content"]

        completion = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        content = completion.choices[0].message.content

        write_cached_response(cache_key, {"content": content}, self._cache_dir)

        logger.info(
            "ModelClient API call",
            extra={"cache_hit": False, "model_name": model, "retry_count": 0},
        )
        return content
```

### Existing `settings` fields used by this story

From `backend/app/core/config.py` (already exists — DO NOT modify):

```python
class Settings(BaseSettings):
    openrouter_api_key: str        # ← used by ModelClient for OpenRouter auth
    bypass_cache: bool = False     # ← used by ModelClient to skip cache (BYPASS_CACHE env var)
    database_url: str = "sqlite:///./freightmind.db"
    cache_dir: str = "./cache"     # ← used by cache.py as the storage directory
```

All three relevant fields (`openrouter_api_key`, `bypass_cache`, `cache_dir`) are already defined. No changes to `config.py` needed.

### Cache directory

`backend/cache/` already exists with a `.gitkeep` (scaffolded in Story 1.1). Cache files (`.json`) are gitignored. The `write_cached_response` function calls `mkdir(parents=True, exist_ok=True)` so it is safe even if the directory is missing.

### OpenRouter API — using openai SDK

The `openai` Python SDK is used to call OpenRouter via `base_url` override (already listed in `pyproject.toml` from Story 1.1). Model names for this project:
- Analytics/SQL: `"meta-llama/llama-3.3-70b-instruct"`
- Vision/Extraction: `"qwen/qwen2.5-vl-72b-instruct"` (Epic 3)

`ModelClient` is model-agnostic — callers pass the model string. No hardcoded model names in `model_client.py`.

### Testing pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.cache import make_cache_key, get_cached_response, write_cached_response
from app.services.model_client import ModelClient
```

**CRITICAL:** `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must appear **before** any `app.*` import — `Settings` validates env on module import. This pattern is established in all previous stories (1.3 through 1.5).

**Mocking OpenRouter for cache miss test:**

```python
@pytest.mark.asyncio
async def test_cache_miss_calls_api_and_writes_cache(tmp_path):
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "SELECT COUNT(*) FROM shipments"

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_openai_cls.return_value = mock_client

        mc = ModelClient(cache_dir=str(tmp_path))
        result = await mc.call("test-model", [{"role": "user", "content": "hello"}], 0.0)

    assert result == "SELECT COUNT(*) FROM shipments"
    # Cache file should now exist
    key = make_cache_key("test-model", [{"role": "user", "content": "hello"}], 0.0)
    cached = get_cached_response(key, str(tmp_path))
    assert cached == {"content": "SELECT COUNT(*) FROM shipments"}
```

**Bypass cache test:**

```python
@pytest.mark.asyncio
async def test_bypass_cache_always_calls_api(tmp_path, monkeypatch):
    monkeypatch.setenv("BYPASS_CACHE", "true")
    # Reimport settings or reload — or test via ModelClient behaviour
    # Pre-seed a cache entry
    key = make_cache_key("test-model", [{"role": "user", "content": "x"}], 0.0)
    write_cached_response(key, {"content": "cached-response"}, str(tmp_path))

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "live-response"

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_openai_cls.return_value = mock_client

        # Inject bypass_cache=True directly to avoid settings reload complexity
        mc = ModelClient(cache_dir=str(tmp_path))
        with patch.object(mc, '_bypass_cache', True):  # or patch settings
            result = await mc.call("test-model", [{"role": "user", "content": "x"}], 0.0)

    assert result == "live-response"
```

> **Note:** The simplest approach for the bypass test is to patch `settings.bypass_cache` directly with `monkeypatch` on the `app.services.model_client.settings` object.

**Enforcement test (no direct openai imports in agents):**

```python
import subprocess

def test_no_openai_import_outside_model_client():
    result = subprocess.run(
        ["grep", "-r", "import openai", "app/agents/", "app/api/"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    assert result.stdout == "", f"Found direct openai imports outside model_client.py:\n{result.stdout}"
```

### Test file naming and structure

- File: `backend/tests/test_story_1_6.py`
- All test classes use `class Test<Feature>:` pattern (from Story 1.1 convention)
- Use `pytest-asyncio` for async tests (already in dev dependencies from Story 1.4)
- Use `tmp_path` pytest fixture for cache directory isolation

### Previous story learnings

From Story 1.5:
- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` at top of test file before any app imports — `Settings` eagerly validates on import.
- Test file naming: `backend/tests/test_story_1_{N}.py`.
- All test classes use `class Test<Feature>:` pattern (no standalone functions).

From Story 1.4:
- `httpx` is already a runtime dependency (installed via `openai` SDK's dependencies) — no need to add separately.
- The `openai` SDK uses `httpx` under the hood; pass `http_client=httpx.AsyncClient(timeout=...)` to control timeout.

From Story 1.1:
- `backend/app/services/__init__.py` already exists — do not recreate it.
- `backend/cache/` directory already exists with `.gitkeep`.
- `uv add pytest-asyncio` if not already in dev deps.

### What this story does NOT implement

- Retry with exponential backoff (Epic 5 — Story 5.2)
- Model fallback on primary model failure (Epic 5 — Story 5.5)
- Rate limit detection (Epic 5 — Story 5.3)

`ModelClient.call()` in this story does **not** retry on failure. Future stories will extend `ModelClient` — keep the implementation clean and extensible.

### References

- Architecture — Backend Services Layout: `backend/app/services/model_client.py` + `cache.py`
- Architecture — Process Patterns — LLM Call Pattern: "ModelClient is Mandatory"
- Architecture — Process Patterns — Cache Key Pattern: `sort_keys=True` + `hashlib.sha256`
- Architecture — Enforcement: "Red flag: `import openai` outside of `model_client.py`"
- Architecture — NFR11: OpenRouter timeout 5s (`httpx.Timeout(5.0)`)
- Architecture — NFR13: SHA-256 cache key with `sort_keys=True`
- Architecture — FR37: Log `cache_hit`, `model_name`, `retry_count` on every LLM call
- Architecture — FR44: `BYPASS_CACHE` env var skips cache entirely
- `backend/app/core/config.py` — `settings.openrouter_api_key`, `settings.bypass_cache`, `settings.cache_dir` (already defined, no changes needed)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Created `backend/app/services/cache.py` with three pure sync functions: `make_cache_key` (SHA-256 via `sort_keys=True` JSON), `get_cached_response` (returns None on miss), `write_cached_response` (atomic write via tmp-rename)
- Created `backend/app/services/model_client.py` with `ModelClient` async class: OpenRouter via openai SDK base_url override, 5s httpx timeout (NFR11), cache-before-call / write-after-call flow, `bypass_cache` via `settings.bypass_cache`, INFO-level logging with `cache_hit`/`model_name`/`retry_count` (FR37)
- `cache_dir` is injected via `__init__` parameter for test isolation using `tmp_path`
- 19 new tests in `test_story_1_6.py`; 90/90 tests pass (19 new + 71 regression)
- Bypass cache test patches `app.services.model_client.settings` directly — avoids Settings re-import complexity
- Architectural enforcement test uses `grep` subprocess to guarantee no `import openai` in agents/ or api/

### File List

- `backend/app/services/cache.py` — new: `make_cache_key`, `get_cached_response`, `write_cached_response`
- `backend/app/services/model_client.py` — new: `ModelClient` async class with cache + OpenRouter integration
- `backend/tests/test_story_1_6.py` — new: 19 tests covering cache round-trip, cache hit/miss, bypass, enforcement

## Change Log

- 2026-03-30: Story created — ready for dev
- 2026-03-30: Implemented Story 1.6 — `cache.py` + `ModelClient` with SHA-256 file cache. 90/90 tests pass.
