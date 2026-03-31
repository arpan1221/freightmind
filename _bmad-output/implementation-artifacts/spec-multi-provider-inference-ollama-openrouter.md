---
title: 'Multi-Provider Inference: Ollama + OpenRouter Configurable Backend'
type: 'feature'
created: '2026-03-31'
status: 'done'
baseline_commit: 'e64ec3824e334ed1197698f754042059be90df39'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `ModelClient` hardcodes OpenRouter as the sole LLM provider, making it impossible to route specific agents to Ollama (local, no rate limits) without forking the client.

**Approach:** Add a per-agent `provider` setting (`"openrouter"` | `"ollama"`) to config; parametrise `ModelClient.__init__` with `base_url` and `api_key`; expose two factory classmethods (`for_analytics`, `for_vision`) that read settings and wire the right endpoint. Call sites swap to the factory. Current intent: analytics → Ollama (`llama3.2:3b`), vision → OpenRouter.

## Boundaries & Constraints

**Always:**
- Both providers use the same OpenAI-SDK-compatible client (`openai.AsyncOpenAI`) — no new HTTP client library.
- Cache, retry, fallback, and streaming logic in `ModelClient` remain unchanged.
- Fallback model uses the same provider as its primary (no cross-provider fallback).
- `openrouter_api_key` stays required while `vision_provider = "openrouter"`.

**Ask First:**
- If cross-provider fallback is needed (Ollama primary → OpenRouter fallback on failure), halt before implementing.

**Never:**
- Do not add a separate OllamaClient class.
- Do not change the `ModelClient.call` / `stream_call` / retry interface.
- Do not add Ollama to `docker-compose.yml` — Ollama runs on the host; the container calls `host.docker.internal`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Analytics via Ollama | `ANALYTICS_PROVIDER=ollama`, `ANALYTICS_MODEL=llama3.2:3b`, Ollama running locally | SQL generation, answer, chart all return normally | Timeout / connection error → `ModelUnavailableError` (existing path) |
| Vision via OpenRouter | `VISION_PROVIDER=openrouter`, `VISION_MODEL=nvidia/nemotron-nano-12b-v2-vl:free` | Extraction succeeds as before | Existing 429/503 handling unchanged |
| Ollama not running | `ANALYTICS_PROVIDER=ollama`, Ollama process down | `ModelUnavailableError` → 503 with message | Existing global handler returns structured error |
| Swap both to OpenRouter | Both providers `= "openrouter"` | Behaves identically to current codebase | No change |

</frozen-after-approval>

## Code Map

- `backend/app/core/config.py` -- add `analytics_provider`, `vision_provider`, `ollama_base_url`; make `openrouter_api_key` optional with `None` default
- `backend/app/services/model_client.py` -- parametrise `__init__` with `base_url`/`api_key`; add `for_analytics()` and `for_vision()` classmethods
- `backend/app/api/routes/analytics.py:169` -- swap `ModelClient()` → `ModelClient.for_analytics()`
- `backend/app/api/routes/documents.py:60` -- swap `ModelClient(timeout=settings.vision_timeout)` → `ModelClient.for_vision(timeout=settings.vision_timeout)`
- `backend/.env.example` -- document new env vars

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/core/config.py` -- add `analytics_provider: str = "ollama"`, `vision_provider: str = "openrouter"`, `ollama_base_url: str = "http://host.docker.internal:11434/v1"`; make `openrouter_api_key: str | None = None`; add validator that raises if `openrouter_api_key` is None when any provider is `"openrouter"` -- providers are now independently configurable without touching model names
- [x] `backend/app/services/model_client.py` -- add `base_url: str` and `api_key: str` params to `__init__` replacing the hardcoded OpenRouter values; add `@classmethod for_analytics(cls, timeout: float = 5.0) -> ModelClient` that resolves `base_url`/`api_key` from `settings.analytics_provider`; add `@classmethod for_vision(cls, timeout: float = 5.0) -> ModelClient` same for vision -- call sites need zero knowledge of provider logic
- [x] `backend/app/api/routes/analytics.py` -- line 169: replace `ModelClient()` with `ModelClient.for_analytics()` -- routes delegate provider selection to the factory
- [x] `backend/app/api/routes/documents.py` -- line 60: replace `ModelClient(timeout=settings.vision_timeout)` with `ModelClient.for_vision(timeout=settings.vision_timeout)` -- same rationale
- [x] `backend/.env.example` -- append `ANALYTICS_PROVIDER=ollama`, `VISION_PROVIDER=openrouter`, `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` with inline comments -- keeps env self-documenting

**Acceptance Criteria:**
- Given `ANALYTICS_PROVIDER=ollama` and Ollama running with `llama3.2:3b`, when `POST /api/query/stream` is called, then the response streams successfully without touching OpenRouter.
- Given `VISION_PROVIDER=openrouter`, when `POST /api/documents/extract` is called, then the OpenRouter vision model is used exactly as before.
- Given `VISION_PROVIDER=openrouter` and `OPENROUTER_API_KEY` is unset, when the app starts, then startup raises a clear `ValueError`.
- Given `ANALYTICS_PROVIDER=ollama` and Ollama is unreachable, when a query is made, then a 503 with `error_type: model_unavailable` is returned.

## Design Notes

Provider resolution inside the classmethods (illustrative — not prescriptive):

```python
@classmethod
def for_analytics(cls, timeout: float = 5.0) -> "ModelClient":
    if settings.analytics_provider == "ollama":
        return cls(base_url=settings.ollama_base_url, api_key="ollama", timeout=timeout)
    return cls(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key, timeout=timeout)
```

`api_key="ollama"` satisfies the SDK's non-None requirement; Ollama ignores it.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/ -x -q` -- expected: all existing tests pass (no regressions)

**Manual checks (if no CLI):**
- With Ollama running (`ollama serve`) and `llama3.2:3b` pulled, set `ANALYTICS_PROVIDER=ollama` and confirm a chat query returns an answer.
- Set `VISION_PROVIDER=openrouter` with a valid key and confirm an invoice upload extracts fields.

## Suggested Review Order

**Provider abstraction — entry point**

- Factory classmethods: where provider selection actually happens.
  [`model_client.py:58`](../../backend/app/services/model_client.py#L58)

- Config: new provider fields with `Literal` types + startup validator.
  [`config.py:19`](../../backend/app/core/config.py#L19)

**Call site changes**

- Analytics route: one-line swap to `for_analytics()`.
  [`analytics.py:169`](../../backend/app/api/routes/analytics.py#L169)

- Documents route: one-line swap to `for_vision(timeout=...)`.
  [`documents.py:60`](../../backend/app/api/routes/documents.py#L60)

**Fallback behaviour change**

- Removed `except RateLimitError: raise` guards — 429 now tries fallback.
  [`model_client.py:115`](../../backend/app/services/model_client.py#L115)

**Tests and config**

- Updated test patches from `ModelClient` constructor to `for_analytics/for_vision`.
  [`test_story_2_1.py:176`](../../backend/tests/test_story_2_1.py#L176)

- New test contracts for 429-triggers-fallback behaviour.
  [`test_story_5_5.py:140`](../../backend/tests/test_story_5_5.py#L140)

- Env example documenting new provider vars.
  [`.env.example:7`](../../backend/.env.example#L7)
