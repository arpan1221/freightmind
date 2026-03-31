# Story 5.4: Invalid or unsafe SQL — structured error with failed query

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a logistics analyst,
I want to receive a clear error message when the system generates SQL that is invalid or unsafe, including the problematic query,
so that I understand what went wrong and can rephrase my question.

## Acceptance Criteria

1. **Verifier rejection (unsafe SQL)**  
   **Given** the Verifier rejects generated SQL (e.g. write/DDL keywords per `AnalyticsVerifier` / NFR8)  
   **When** the rejection is handled in the analytics route  
   **Then** the HTTP response uses the shared **`ErrorResponse`** envelope from Story 5.1 with **`error_type: "unsafe_sql"`**, a human-readable **`message`**, and **`detail.sql`** containing the **rejected query string** (full query, not only a truncated prefix) (FR32)  
   **And** the response is **non-2xx** (recommend **400**) so clients that only treat 2xx as success behave correctly.

2. **SQL execution failure (invalid SQL)**  
   **Given** the Verifier passes but SQLite/SQLAlchemy raises when executing the statement (syntax error, unknown column, etc.)  
   **When** the route catches that failure  
   **Then** the response is an **`ErrorResponse`** with **`error_type: "sql_execution_error"`**, a safe human **`message`** (no raw stack trace in JSON), and **`detail.sql`** containing the **failed query** that was executed (FR32)  
   **And** the response is **non-2xx** (recommend **422** for “generated SQL not executable”).

3. **Contract alignment**  
   **Given** Stories **5.1**–**5.3** define `ErrorResponse` (`error`, `error_type`, `message`, optional `detail`, optional `retry_after`)  
   **When** implementing this story  
   **Then** reuse the same model/helpers — do not invent a parallel error shape for analytics-only.

## Tasks / Subtasks

- [x] **Task 1 — Schema & HTTP contract (AC: 1–3)**  
  - [x] Confirm `ErrorResponse` in `backend/app/schemas/common.py` includes optional **`detail: dict | None`** (or equivalent) able to carry **`{"sql": "<query>"}`** per 5.1; extend if missing.  
  - [x] Document stable strings: **`unsafe_sql`**, **`sql_execution_error`**.  
  - [x] Update **`POST /api/query`** OpenAPI `responses` metadata to list **400** / **422** (or chosen codes) with `ErrorResponse`.

- [x] **Task 2 — `analytics.py` behaviour (AC: 1–2)**  
  - [x] **Unsafe path:** On **`ValueError`** from `verifier.verify(sql)` (current pattern), capture the **full** `sql` string (variable exists before `verify`); return **`JSONResponse`** with **`ErrorResponse`**, status **400**, **`error_type: "unsafe_sql"`**, **`detail.sql` = sql**.  
    - Remove or avoid returning **200** with `AnalyticsQueryResponse.error="unsafe_sql"` for this case if the epic requires **`ErrorResponse`** — avoid two competing contracts.  
  - [x] **Execution path:** Narrow the broad **`except Exception`** around `db.execute(text(safe_sql))` (or equivalent) so **SQLAlchemy database/API errors** map to **`sql_execution_error`** with **`detail.sql = safe_sql`**.  
    - Use appropriate exception types (e.g. `sqlalchemy.exc.StatementError`, `OperationalError`, `ProgrammingError` — align with SQLite/SQLAlchemy 2.x docs).  
    - Keep **non-SQL** failures (e.g. bugs, unexpected errors) on a separate path (e.g. existing **`query_failed`** / **500** / global handler) so verifier vs execution vs internal errors stay distinguishable in tests.  
  - [x] **Logging:** Log server-side with structured context; **never** put secrets in JSON; **`detail.sql`** is intentional transparency for the analyst (FR32).

- [x] **Task 3 — Frontend consumption (AC: 1–2)**  
  - [x] **`useAnalytics`:** On **`axios`** error responses with **`response.data`** matching **`ErrorResponse`**, surface **`message`** to the user and attach **`detail.sql`** to assistant message state (or equivalent) so the chat can show the failed query.  
  - [x] **`ChatPanel` / types:** Extend types if needed so **`detail?.sql`** can render (e.g. reuse collapsible SQL disclosure pattern from successful answers where it fits; full polish may overlap **Story 5.6** — minimum is visible failed SQL + message).  
  - [x] Update **`frontend/src/types/api.ts`** for `ErrorResponse` parity with backend.

- [x] **Task 4 — Tests**  
  - [x] Add **`backend/tests/test_story_5_4.py`**:  
    - Mock pipeline so **`generate_sql`** returns a string that **`AnalyticsVerifier` rejects** → assert **400**, body **`error_type == "unsafe_sql"`**, **`detail["sql"]`** equals that string.  
    - Mock **`generate_sql`** to return syntactically invalid SQL that passes the verifier regex (if needed, use a query SQLite rejects, e.g. bad column) → assert **`sql_execution_error`** and **`detail["sql"]`**.  
  - [x] Adjust any tests that currently expect **200** + `error: "unsafe_sql"` on the analytics response model.

### Review Findings

- [x] [Review][Patch] Clear FastAPI `dependency_overrides` after Story 5.4 tests [`backend/tests/test_story_5_4.py`] — fixed 2026-03-31 (`clear_overrides` fixture, same pattern as `test_story_4_2.py`).

- [x] [Review][Defer] Broad `SQLAlchemyError` on `db.execute` maps infra failures (e.g. database locked) to `sql_execution_error` — same envelope as bad SQL; acceptable for FR32 v1; revisit if product wants distinct `error_type` for infra.

## Dev Notes

### Brownfield — current behaviour (do not preserve blindly)

| Location | Today | Gap vs FR32 / epic |
|----------|--------|---------------------|
| `backend/app/api/routes/analytics.py` | On `ValueError`, returns **200** + `AnalyticsQueryResponse` with `error="unsafe_sql"`, **`sql=""`** | No **`ErrorResponse`**; **no failed query** in payload |
| Same | Broad `except Exception` → `query_failed` with **empty `sql`** | Execution errors not typed as **`sql_execution_error`**; no **`detail.sql`** |
| `backend/app/agents/analytics/verifier.py` | Raises `ValueError` with truncated snippet `sql[:200]` | Response should still expose **full** SQL in **`detail.sql`** (message can stay short) |

### Dependencies

| Story | Why it matters |
|-------|----------------|
| **5.1** | `ErrorResponse` shape, `error_type`, `detail`, global handlers |
| **5.2 / 5.3** | Typed LLM failures — do not confuse SQL errors with `rate_limit` / `model_unavailable` |

### Architecture & NFR alignment

- **NFR7 / NFR8:** Verifier remains the gate before `execute`; no user text in SQL strings.  
- **Architecture:** Single `ErrorResponse` in `schemas/common.py` [Source: `_bmad-output/planning-artifacts/architecture.md`].  
- Epic text mentions keywords “targeting **shipments**”; **implementation** uses a **global** keyword blocklist on the whole statement — story tests should match **actual** `AnalyticsVerifier` behaviour to avoid false “done”.

### Files likely touched

| Path | Role |
|------|------|
| `backend/app/schemas/common.py` | `ErrorResponse.detail` if needed |
| `backend/app/api/routes/analytics.py` | Error branches, status codes, stop dual contract for unsafe SQL |
| `backend/app/agents/analytics/verifier.py` | Optional: clarify exception type or message (still raise before execute) |
| `frontend/src/hooks/useAnalytics.ts` | Parse axios error `ErrorResponse` |
| `frontend/src/components/ChatPanel.tsx` | Display error + optional `detail.sql` |
| `frontend/src/types/api.ts` | `ErrorResponse` + message shape |
| `backend/tests/test_story_5_4.py` | New |

### Anti-patterns

- Do not return **`detail.sql`** for unrelated errors (LLM outage, rate limit).  
- Do not leak internal Python exception strings in **`message`** for production-minded responses — log full trace server-side only.  
- Do not duplicate a second error JSON schema only for analytics.

### Previous story intelligence

- [Source: `_bmad-output/implementation-artifacts/5-1-fastapi-global-error-handler-errorresponse-envelope.md`] — canonical envelope.  
- [Source: `_bmad-output/implementation-artifacts/5-3-rate-limit-detection-and-structured-response-with-retry-after.md`] — boundary pattern: typed failure → HTTP `ErrorResponse`.  
- [Source: `backend/tests/test_story_4_2.py`] — DB setup + `TestClient` patterns for analytics.

### Git intelligence summary

Recent history is shallow; rely on file-level analysis above rather than commit archaeology.

### Latest tech information

- SQLAlchemy 2.x: prefer catching **`SQLAlchemyError`** subclasses rather than bare `Exception` for execution failures; map only those to **`sql_execution_error`**.  
- FastAPI: use **`JSONResponse(status_code=..., content=ErrorResponse(...).model_dump())`** when mixing success `response_model` with error branches.

### Project context reference

No `project-context.md` in repo; use this file + `epics.md` Story 5.4 + `architecture.md`.

### References

- [Epics — Story 5.4](_bmad-output/planning-artifacts/epics.md)  
- [PRD — FR32](_bmad-output/planning-artifacts/prd.md)  
- [Architecture — ErrorResponse, Verifier](_bmad-output/planning-artifacts/architecture.md)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Implemented `POST /api/query` unsafe SQL → **400** `ErrorResponse` (`unsafe_sql`, `detail.sql` full rejected query); verified SQL execution failure → **422** `sql_execution_error` (`SQLAlchemyError` on `db.execute` only). Other failures remain **200** `query_failed` on `AnalyticsQueryResponse` where applicable.
- Frontend: `useAnalytics` parses axios `ErrorResponse`; `ChatPanel` shows message + `SqlDisclosure` for `detail.sql`.
- Full backend test suite passed (343 tests).

### File List

- `backend/app/api/routes/analytics.py`
- `backend/app/schemas/common.py`
- `backend/tests/test_story_5_4.py`
- `backend/tests/test_story_2_1.py`
- `backend/tests/test_story_2_2.py`
- `frontend/src/hooks/useAnalytics.ts`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/types/api.ts`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-03-30: Story 5.4 — structured `ErrorResponse` for unsafe SQL (400) and SQL execution errors (422); frontend chat display; tests added/updated.
- 2026-03-31: Code review — `clear_overrides` fixture in `test_story_5_4.py`; story marked done.

---

## Story completion status

- **Status:** done  
- **Note:** Code review patch applied; ACs satisfied.
