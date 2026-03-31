# Story 5.1: fastapi-global-error-handler-errorresponse-envelope

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a developer,
I want all API errors to return a consistent `ErrorResponse` JSON shape regardless of where the failure occurs,
so that the frontend always receives structured, parseable errors — never a raw Python traceback or FastAPI’s default `{"detail": ...}`.

## Acceptance Criteria

1. **Unhandled exceptions**  
   **Given** any unhandled exception occurs in a route handler  
   **When** FastAPI processes the error  
   **Then** the response body matches `ErrorResponse`: `error` = `true`, `error_type` = a stable string identifier, `message` = human-readable text, `detail` = optional structured payload (object)  
   **And** the default bare traceback response is not returned (FR29).

2. **HTTPException**  
   **Given** a handler raises `HTTPException` (or Starlette `HTTPException`)  
   **When** the global handler runs  
   **Then** the body uses the same `ErrorResponse` envelope — not FastAPI’s `{"detail": "..."}` only (FR29).  
   *Note:* `app/main.py` already registers `@app.exception_handler(StarletteHTTPException)`; align its payload with the final `ErrorResponse` model.

3. **Validation errors**  
   **Given** a malformed request body (Pydantic validation failure on a route)  
   **When** FastAPI processes `RequestValidationError`  
   **Then** the response uses `ErrorResponse` with `error_type: "validation_error"` and `detail` containing enough context for debugging (e.g. simplified field errors) — not the default Pydantic/FastAPI validation JSON alone.

4. **LLM parse failures (in-route)**  
   **Given** application code catches LLM output that cannot be parsed to the expected schema  
   **When** the route returns an error response  
   **Then** it uses `ErrorResponse` with `error_type: "llm_parse_error"` (or delegates to the global handler via raised exception) — the process must not crash with an unhandled exception (FR29).  
   *Scope for 5.1:* At minimum, define the contract and ensure **one** representative path or a small helper is documented; full ModelClient integration is Epic 5.2+.

## Tasks / Subtasks

- [x] **Task 1 — `ErrorResponse` schema (AC: 1–3)**  
  - [x] Evolve `backend/app/schemas/common.py` `ErrorResponse` to match the epic contract: boolean `error`, string `error_type`, string `message`, optional `detail` (dict / JSON-serializable), optional `retry_after` (int | null). Use field defaults so successful responses elsewhere are unaffected.  
  - [x] Add Pydantic config so JSON output uses the agreed keys; document breaking change for any client that expected `error` as a string — update `frontend/src/types/api.ts` `ErrorResponse` in the same story.  
  - [x] Grep the repo for `ErrorResponse(` and `model_dump()` usages; update constructors (`main.py`, `extraction.py`, tests).

- [x] **Task 2 — Global handlers in `main.py` (AC: 1–3)**  
  - [x] Keep or refactor `StarletteHTTPException` handler to emit the new shape (`error_type` e.g. `http_error` or map from status code).  
  - [x] Register `fastapi.exceptions.RequestValidationError` handler → `validation_error`, status 422.  
  - [x] Register broad `Exception` handler for unexpected errors → generic `error_type` (e.g. `internal_error`), log server-side with `logger.exception`, **do not** leak tracebacks in `message`/`detail` in production-minded code (stack in logs only).

- [x] **Task 3 — LLM parse error contract (AC: 4)**  
  - [x] Either: document that routes must return `JSONResponse` with `llm_parse_error`, or add a tiny helper `def llm_parse_error_response(msg: str, detail: dict | None = None) -> JSONResponse` in `schemas/common.py` or `api` utils — ensure one caller is updated or a test documents the pattern.

- [x] **Task 4 — Tests**  
  - [x] Add or extend `backend/tests/` (e.g. `test_story_5_1.py`): unknown route → 404 → new ErrorResponse shape; POST invalid body to an existing JSON route → 422 → `validation_error`; optional forced 500 in a test-only route **or** patch route to raise — assert envelope, no `"detail"` key as sole FastAPI default (define assertions explicitly).  
  - [x] Update `test_story_1_1.py` assertions if they pin the old three-field schema.

## Dev Notes

### Current state (brownfield)

- `backend/app/main.py` — `http_exception_handler` returns `ErrorResponse` with fields `error`, `message`, `retry_after` (legacy string `error`).  
- `backend/app/schemas/common.py` — `ErrorResponse` uses optional `error: str` (semantic clash with epic’s `error: true`).  
- `backend/app/api/routes/extraction.py` — 404 `JSONResponse` + `ErrorResponse(...)`.  
- `frontend/src/types/api.ts` — `ErrorResponse` mirrors legacy backend.  
- Analytics routes often return **200** with `error` inside `AnalyticsQueryResponse` — **out of scope** for this story unless PRD requires unification; do not break analytics JSON shape.

### Architecture compliance

- Single shared `ErrorResponse` in `schemas/common.py` [Source: `_bmad-output/planning-artifacts/architecture.md`].  
- Structured logging on server; user-facing `message` stays safe [Source: epics FR29].

### Technical requirements

| Topic | Requirement |
|--------|----------------|
| FastAPI | `RequestValidationError` from `fastapi.exceptions`; import `HTTPException` from `fastapi` if aligning handlers. |
| Status codes | Map validation → 422; client errors via HTTPException status; unexpected → 500 unless epic says otherwise. |
| JSON | `JSONResponse(content=model.model_dump())` or `response_model` consistency — ensure datetime/Decimal not in `detail` without serialization. |

### Files likely touched

| Path | Role |
|------|------|
| `backend/app/schemas/common.py` | `ErrorResponse` model |
| `backend/app/main.py` | Exception handlers |
| `backend/app/api/routes/extraction.py` | 404 body |
| `frontend/src/types/api.ts` | TS interface |
| `backend/tests/test_story_1_1.py`, new `test_story_5_1.py` | Assertions |

### Testing standards

- pytest + `TestClient`; follow existing env `OPENROUTER_API_KEY` pattern for imports.

### Previous story intelligence

- **4.1** completed dual-table analytics and short-circuits for empty confirmations — do not regress `POST /api/query` success/error field names inside `AnalyticsQueryResponse`.

### Project context reference

- No `project-context.md`; use this file + `epics.md` Story 5.1 + `architecture.md` error sections.

### Latest tech information

- FastAPI 0.115+ / Starlette — exception handler registration order can matter; register specific handlers before the generic `Exception` handler.

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

_(none)_

### Completion Notes List

- Implemented `ErrorResponse` with `error: bool`, `error_type`, `message`, optional `detail` and `retry_after`.
- Registered `RequestValidationError` → `validation_error` (422) and broad `Exception` → `internal_error` (500) with safe client message; HTTP errors use `http_error` with `detail.status_code`.
- Added `app/api/error_responses.py::llm_parse_error_response` plus unit test; 500 envelope test uses `TestClient(..., raise_server_exceptions=False)` because Starlette otherwise re-raises route exceptions even when the global handler returns JSON.
- Updated extraction 404 and `test_story_3_5` / `test_story_1_1` for the new shape; frontend `ErrorResponse` type aligned.

### File List

- `backend/app/schemas/common.py`
- `backend/app/main.py`
- `backend/app/api/error_responses.py`
- `backend/app/api/routes/extraction.py`
- `backend/tests/test_story_5_1.py`
- `backend/tests/test_story_1_1.py`
- `backend/tests/test_story_3_5.py`
- `frontend/src/types/api.ts`

### Change Log

- 2026-03-30: Story 5.1 — unified `ErrorResponse` envelope, global validation/internal handlers, `llm_parse_error_response` helper, tests.

---

### Review Findings

- [x] [Review][Dismiss] **BMad code review (2026-03-30)** — Clean review after triage: no `decision-needed`, `patch`, or `defer` items. `pytest tests/test_story_5_1.py` passed.

## Story completion status

- **Status:** done  
- **Note:** Implementation complete; full backend pytest suite passing (327 tests).
