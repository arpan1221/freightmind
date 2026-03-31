# Story 5.2: ModelClient retry with corrective instruction

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created. -->

## Story

As a developer,
I want `ModelClient` to automatically retry a failed LLM call at least once, appending a corrective instruction to the messages,
so that transient LLM failures and format errors are self-corrected before surfacing an error to the user.

## Acceptance Criteria

1. **First parse / validation failure (FR30)**  
   **Given** `ModelClient` obtains a response string that fails an optional caller-supplied validation step (e.g. invalid JSON where JSON was required)  
   **When** that is the first failure for this logical `call`  
   **Then** the client waits **1 second**, then issues a new API request with the **original messages plus** a corrective instruction (e.g. asking for valid JSON only)  
   **And** structured logging records **`retry_count`** appropriate to the attempt (see Dev Notes: FR37).

2. **Second and third failures — backoff**  
   **Given** the first retry still fails validation  
   **When** failures continue consecutively  
   **Then** the client waits **2 seconds** before the next attempt, then **4 seconds** before a further attempt (same corrective-append pattern).

3. **Exhaustion**  
   **Given** all retry attempts are exhausted (see attempt budget below)  
   **When** the last attempt still fails validation or the API raises  
   **Then** `ModelClient` **raises** an exception suitable for route handlers (Epic: never return raw OpenRouter payloads to the client); routes continue to map failures to structured errors per **Story 5.1** / FR29 when integrated.

4. **Scope boundary**  
   **Given** this story focuses on **retry-after-validation** and **transient retry** behaviour  
   **When** compared to **Story 5.3** (rate limits / 429) and **Story 5.5** (fallback model)  
   **Then** those behaviours remain **out of scope** here unless a minimal hook is required — document any intentional stubs.

## Tasks / Subtasks

- [x] **Task 1 — API design (AC: 1–3)**  
  - [x] Extend `ModelClient.call(...)` (or add a dedicated method used by routes) with an optional way to run a **post-response check** that can fail without a successful parse — e.g. `validate: Callable[[str], None]` that raises on bad output, or an async equivalent. Callers that do not pass `validate` keep today’s single-shot behaviour (no retries for parse).  
  - [x] Implement **attempt loop** with max attempts and sleeps **1s → 2s → 4s** before attempts 2–4 (after a failure). Document exact attempt count in code comments (recommended: **4** attempts total: initial + 3 retries, matching epics text).  
  - [x] Append a **corrective** user or system message on retries — text should be loaded from `backend/app/prompts/` as a **`.txt` file** (FR40), e.g. `model_retry_corrective.txt`, not a large inline string in Python.

- [x] **Task 2 — Logging (FR37)**  
  - [x] Every log line for a model call must include `cache_hit`, `model_name`, and **`retry_count`** (0 on first attempt, 1 after first retry, etc.).  
  - [x] On final failure before raise, log at **warning** or **error** with `retry_count` max.

- [x] **Task 3 — Cache interaction**  
  - [x] Define behaviour when a **cache hit** returns content that fails `validate`: do **not** infinite-loop on bad cache; either skip cache for subsequent attempts in the same logical call or bypass cache for retry rounds. Document the chosen rule in code comments.

- [x] **Task 4 — Tests**  
  - [x] Add `backend/tests/test_story_5_2.py`: mock `AsyncOpenAI` / `chat.completions.create` to return failing-then-passing content **or** always failing to assert exception after 4 attempts.  
  - [x] **Patch `asyncio.sleep`** (or inject a sleep callable) so tests run fast.  
  - [x] Assert backoff intervals (1, 2, 4) are requested in order when all attempts fail.  
  - [x] Assert `retry_count` in log `extra` or cap log records.

- [x] **Task 5 — Coordination with Story 5.1**  
  - [x] If **5.1** is not merged yet, keep `ModelClient` raising plain exceptions; document that **routes** will map to `ErrorResponse` in 5.1+. If 5.1 is already done, prefer raising a small domain exception type that the global handler recognises, without breaking analytics’ existing 200+`error` field pattern.

## Dev Notes

### Behaviour table (recommended)

| Attempt | Sleep before | `retry_count` (log) |
|--------|----------------|---------------------|
| 1 | — | 0 |
| 2 | 1s | 1 |
| 3 | 2s | 2 |
| 4 | 4s | 3 |

After attempt 4 still invalid → raise.

### Current implementation

- [Source: `backend/app/services/model_client.py`] — `ModelClient.call` performs cache lookup, single OpenRouter call, cache write, logs `retry_count: 0` only. Module docstring states retry/fallback are Epic 5 scope.

### Architecture compliance

- **ModelClient is mandatory gateway** for LLM calls [Source: `_bmad-output/planning-artifacts/epics.md` — Additional Requirements].  
- **Prompt registry:** corrective text in `app/prompts/*.txt` [FR40].  
- **Structured logging** JSON-friendly `extra=` fields [Source: architecture / FR37].

### Previous story intelligence

- **Story 5.1** (`5-1-fastapi-global-error-handler-errorresponse-envelope.md`): defines `ErrorResponse` envelope and global handlers — align exception types and messages so 5.2 failures are not double-wrapped. Analytics routes today return **200** with `error` inside body; do not change that contract in 5.2 unless 5.1 explicitly unifies.

- **Story 1.6 / cache:** `BYPASS_CACHE`, `make_cache_key`, `write_cached_response` — retry path must not corrupt cache keys or write bad responses as success.

### File structure (expected touches)

| File | Purpose |
|------|---------|
| `backend/app/services/model_client.py` | Retry loop, validate hook, logging |
| `backend/app/prompts/model_retry_corrective.txt` (name may vary) | Corrective instruction text |
| `backend/tests/test_story_5_2.py` | Unit/integration tests with mocks |

### Testing standards

- `pytest` + `pytest-asyncio` for async tests; mock network I/O only.  
- No live OpenRouter calls in CI.

### References

- Epic Story 5.2 — [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 5]  
- FR30, FR37 — same file, Requirements Inventory  
- NFR11 — 5s timeout already on httpx client in `ModelClient.__init__`

### Project context reference

- No `project-context.md` in repo.

### Git intelligence summary

- Follow patterns from `test_story_2_1.py` (mock `ModelClient`) and any existing `model_client` tests if present.

### Latest technical notes

- Use `asyncio.sleep` for delays; in tests patch to no-op or record call order.  
- OpenAI SDK: `openai.AsyncOpenAI` — keep async throughout.

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

_(none)_

### Completion Notes List

- Implemented optional keyword-only `validate: Callable[[str], None] | None` on `ModelClient.call`. Without it, behaviour matches pre–5.2 single-shot cache + API path (`_call_single_shot`).
- With `validate`: up to four attempts, backoff 1s / 2s / 4s via `asyncio.sleep`, corrective user message from `load_prompt("model_retry_corrective")`. Successful live responses cached under the **base** `make_cache_key(model, messages, temperature)` so callers keep a stable key.
- Bad cache entries: attempt 0 may read cache; if `validate` fails, later attempts skip cache read and call the API (documented in `_call_with_validation`).
- Wired `validate` for JSON-shaped outputs: `AnalyticsPlanner.classify_intent`, `ExtractionExecutor.extract`, `_generate_follow_ups`, `_generate_chart_config` in `analytics.py`.
- `ExtractionExecutor` still wraps final `json.loads` in `ValueError` for mocked `client.call` in tests that bypass `validate`.

### File List

- `backend/app/services/model_client.py`
- `backend/app/prompts/model_retry_corrective.txt`
- `backend/app/agents/analytics/planner.py`
- `backend/app/agents/extraction/executor.py`
- `backend/app/api/routes/analytics.py`
- `backend/tests/test_story_5_2.py`

### Change Log

- Story 5.2: ModelClient validation retries with corrective prompt; tests and call-site wiring for JSON outputs.

### Review Findings

- [x] [Review][Dismiss] **BMad code review (2026-03-30)** — Clean review after triage: no `decision-needed`, `patch`, or `defer` items. `pytest tests/test_story_5_2.py` passed.

## Story completion status

- **Status:** done  
- **Note:** Implementation complete; full backend pytest suite passing.
