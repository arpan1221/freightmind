# Story 5.3: Rate limit detection and structured response with retry_after

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a logistics analyst,
I want to receive a clear message when the API rate limit is hit, including how long I need to wait before retrying,
so that I know the system is temporarily constrained and when it will recover.

## Acceptance Criteria

1. **Given** the OpenRouter API returns a **429** rate limit response  
   **When** `ModelClient` handles the failed completion call  
   **Then** the failure surfaces in a way the API can return an **`ErrorResponse`** with `error_type: "rate_limit"`, a human-readable `message`, and **`retry_after`** (integer seconds) (FR31)  
   **And** handling completes within **5 seconds** of the HTTP client timeout boundary (NFR11 — align with existing `ModelClient` timeout, typically 5s).

2. **Given** the OpenRouter API is **unreachable** (connection error / read timeout before any usable response)  
   **When** `ModelClient` detects that failure mode  
   **Then** the failure surfaces so the API can return an **`ErrorResponse`** with `error_type: "model_unavailable"` within the same overall time budget (NFR11).

## Tasks / Subtasks

- [x] **Task 1 — Contract alignment with Story 5.1 (AC: 1–2)**  
  - [x] Confirm `ErrorResponse` in `backend/app/schemas/common.py` includes **`error_type`**, optional **`retry_after`**, and boolean/error semantics per `_bmad-output/implementation-artifacts/5-1-fastapi-global-error-handler-errorresponse-envelope.md`. If 5.1 is not merged yet, define the minimal fields needed for FR31 in this story’s branch and coordinate with 5.1.  
  - [x] Document the mapping: **`rate_limit`** ↔ 429 + optional **`Retry-After`** header; **`model_unavailable`** ↔ connection/timeout/DNS failures and other non-429 transport errors from the OpenAI-compatible client.

- [x] **Task 2 — `ModelClient` error handling (AC: 1–2)**  
  - [x] In `backend/app/services/model_client.py`, wrap `chat.completions.create` in logic that:  
    - Intercepts **HTTP 429** from the OpenAI SDK (typically `openai.APIStatusError` or equivalent with `status_code == 429`).  
    - Parses **`retry_after`**: prefer HTTP **`Retry-After`** (seconds or HTTP-date per spec); if missing, use a **documented default** (e.g. `60`) and log that a default was used.  
    - Raises or returns a **typed failure** that routes can convert to `ErrorResponse` — **recommended:** small exceptions in `backend/app/core/exceptions.py`, e.g. `RateLimitError(retry_after: int)` and `ModelUnavailableError(message: str)` rather than changing `call()` to return `str | ErrorResponse` (keeps call sites simple).  
  - [x] Map **connection errors**, **`httpx.TimeoutException`**, and similar to **`model_unavailable`** (not `rate_limit`).  
  - [x] Do **not** break cache hit path — errors apply only to live API calls.  
  - [x] Preserve structured logging (`cache_hit`, `model_name`, `retry_count`) where applicable; increment or document **`retry_count`** if this story layers on 5.2 behaviour.

- [x] **Task 3 — Route integration (minimal surface)**  
  - [x] At least **one** consumer path (e.g. `POST /api/query` or a thin helper used by analytics + extraction) catches the new exceptions and returns **`JSONResponse`** / `ErrorResponse` with correct **`error_type`** and **`retry_after`**.  
  - [x] Prefer a **shared helper** `def llm_failure_to_response(exc: Exception) -> JSONResponse` (or similar) in `schemas/common.py` or `api` utils to avoid duplicating mapping in every route.  
  - [x] **Out of scope for 5.3 alone:** full migration of every LLM call site — story is complete if ModelClient throws typed errors and **one** end-to-end path proves the JSON shape; follow-up can broaden coverage.

- [x] **Task 4 — Tests**  
  - [x] Add `backend/tests/test_story_5_3.py`: mock `AsyncOpenAI` / completion to raise **429** with a controllable **`Retry-After`** (or SDK-equivalent attributes) → assert raised exception or HTTP body contains **`rate_limit`** and expected **`retry_after`**.  
  - [x] Mock **timeout** or **connection refused** → assert **`model_unavailable`**.  
  - [x] Use **`pytest.mark.asyncio`** / existing async patterns from `test_story_1_6.py` (patch `ModelClient` internals or inject mock client).

## Dev Notes

### Epic wording vs implementation

The epic says ModelClient “**returns**” `ErrorResponse`; in this codebase **`ModelClient.call()` returns `str`**. Preferred pattern: **typed exceptions** (or a small `Result` type) emitted from `ModelClient`, **converted to `ErrorResponse` at the HTTP boundary** — matches FastAPI style and keeps the client usable from non-HTTP code (tests, batch jobs).

### Dependencies

| Story | Why it matters |
|-------|----------------|
| **5.1** | Final `ErrorResponse` shape (`error_type`, `retry_after`, etc.) and global handlers |
| **5.2** | Retry/backoff may interact with 429 — ensure no infinite retry on rate limit without backoff; coordinate if both land together |

### OpenRouter / SDK hints

- OpenAI Python SDK v1+ often raises **`APIStatusError`** with **`status_code`** and **`response`** for HTTP errors. Inspect **`response.headers`** for **`retry-after`**.  
- Normalize **`retry_after`** to **integer seconds** for JSON (if header is a date string, parse to seconds or fall back to default).

### Architecture references

- [Source: `_bmad-output/planning-artifacts/architecture.md`] — `ErrorResponse` single model; ModelClient owns OpenRouter access.  
- [Source: `_bmad-output/planning-artifacts/prd.md`] — example rate limit JSON with `retry_after`.  
- NFR11: structured response within **5s** of timeout — `ModelClient` already uses **`httpx.Timeout`** (default **5.0** in constructor); do not raise client timeout so high that NFR11 is violated.

### Files likely touched

| Path | Role |
|------|------|
| `backend/app/services/model_client.py` | Catch 429 / transport errors; raise typed errors |
| `backend/app/core/exceptions.py` | New exception classes (if not present) |
| `backend/app/schemas/common.py` | `ErrorResponse` / helpers (may be 5.1) |
| `backend/app/api/routes/analytics.py` and/or `extraction.py` | Catch and map to JSON |
| `frontend/src/types/api.ts` | Mirror `error_type`, `retry_after` if not done in 5.1 |
| `backend/tests/test_story_5_3.py` | New |

### Anti-patterns

- Do not leak OpenRouter raw response bodies or API keys in `message`.  
- Do not treat **every** 5xx from OpenRouter as `rate_limit` — only **429** (unless product says otherwise).  
- Do not add synchronous blocking sleeps in `ModelClient` for rate limit “recovery” — the client only **reports** `retry_after`; **Story 5.6** drives countdown UI.

### Previous story intelligence

- [Source: `_bmad-output/implementation-artifacts/5-1-fastapi-global-error-handler-errorresponse-envelope.md`] — ErrorResponse evolution and frontend type updates.  
- [Source: `backend/tests/test_story_1_6.py`] — patterns for patching `openai.AsyncOpenAI`.

### Testing standards

- Mock external HTTP; no live OpenRouter in unit tests.  
- Assert **stable** `error_type` strings for FR31 / frontend contracts.

### References

- [Epics — Story 5.3](_bmad-output/planning-artifacts/epics.md)  
- [PRD — FR31, error shape](_bmad-output/planning-artifacts/prd.md)  
- [Architecture — ErrorResponse, ModelClient](_bmad-output/planning-artifacts/architecture.md)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Added `RateLimitError` / `ModelUnavailableError` and FastAPI handlers in `main.py` (429 / 503 + `ErrorResponse` JSON).
- `ModelClient._completion_create` maps `APIStatusError` (429 vs other), `APIConnectionError`, `APITimeoutError`, and `httpx` timeout/request errors; `retry_after_seconds_from_response` parses `Retry-After` with default **60** when absent.
- `analytics.post_query` re-raises the two LLM errors so they are not swallowed by broad `except Exception` (including `classify_intent`).
- Tests: `test_story_5_3.py` (retry-after parsing, ModelClient mocks, `POST /api/query` envelope via patched `AnalyticsPlanner`).

### File List

- `backend/app/core/exceptions.py` — new
- `backend/app/core/retry_after.py` — new
- `backend/app/services/model_client.py` — `_completion_create`, SDK error mapping
- `backend/app/main.py` — `RateLimitError` / `ModelUnavailableError` handlers
- `backend/app/api/routes/analytics.py` — re-raise LLM errors from classify + main try
- `backend/tests/test_story_5_3.py` — new

### Change Log

- 2026-03-31: Implemented FR31 rate-limit and model-unavailable paths; added tests.

---

### Review Findings

- [x] [Review][Dismiss] **BMad code review (2026-03-30)** — Clean review after triage: no `decision-needed`, `patch`, or `defer` items. `pytest tests/test_story_5_3.py` passed.

## Story completion status

- **Status:** done  
- **Note:** Implementation complete; code review completed.
