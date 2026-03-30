# Story 2.4: Stateless Follow-Up Query with Previous SQL Context

Status: review

## Story

As a logistics analyst,
I want to ask a follow-up question that refines a previous query by adding a filter, changing a grouping, or adjusting a time window,
So that I can iteratively explore data without restarting from scratch.

## Acceptance Criteria

1. **Given** a previous query returned SQL and results
   **When** `POST /api/query` is called with `{"question": "Filter that to Air shipments only", "previous_sql": "<prior SQL>"}`
   **Then** the Planner uses `previous_sql` as context to generate a refined question
   **And** the response returns refined results with updated SQL, table, and chart (FR5)

2. **Given** `previous_sql` is omitted from the request
   **When** `POST /api/query` is called
   **Then** the system treats it as a fresh query with no prior context (graceful null handling)

3. **Given** the backend processes the follow-up
   **When** the code is inspected
   **Then** no server-side session state is maintained — `previous_sql` in the request body is the sole source of context

## Tasks / Subtasks

- [x] Task 1: Update `AnalyticsPlanner.plan()` to include `previous_sql` in prompt context (AC: 1, 2)
  - [x] In `backend/app/agents/analytics/planner.py`, update `plan()` to build `user_content` using the same pattern as `executor.py`: if `previous_sql` is provided, prepend `"Previous SQL:\n{previous_sql}\n\nNew question:\n{question}"`; otherwise pass `question` only
  - [x] The `analytics_system.txt` prompt already instructs the model to handle follow-up context — no prompt file change needed

- [x] Task 2: Implement `useAnalytics` hook with `previousSql` state tracking (AC: 1, 2, 3)
  - [x] Implement `frontend/src/hooks/useAnalytics.ts` — see Dev Notes for full implementation
  - [x] State: `isQuerying: boolean`, `result: AnalyticsQueryResponse | null`, `error: string | null`, `previousSql: string | null`
  - [x] Expose `query(question: string)` — sends `{question, previous_sql: previousSql}` to `POST /api/query`
  - [x] On success: store `result.sql` in `previousSql` (enables next follow-up)
  - [x] Expose `reset()` — clears all state including `previousSql` (fresh conversation start)
  - [x] Use `isQuerying` boolean (not a shared `isLoading`)

- [x] Task 3: Write tests (AC: 1, 2, 3)
  - [x] Create `backend/tests/test_story_2_4.py`
  - [x] Test: `AnalyticsPlanner.plan()` with `previous_sql` includes it in the messages `user` content
  - [x] Test: `AnalyticsPlanner.plan()` without `previous_sql` sends only the question (graceful null)
  - [x] Test: `POST /api/query` with `previous_sql` in body — passes it through to planner and executor
  - [x] Test: `POST /api/query` without `previous_sql` — processes as fresh query, no error

## Dev Notes

### What Already Exists — Critical Context

**DO NOT reinvent or re-implement these — they already work correctly:**

| Component | Location | Status |
|-----------|----------|--------|
| `AnalyticsQueryRequest.previous_sql: str \| None = None` | `backend/app/schemas/analytics.py:6` | ✅ Already exists |
| `post_query()` passes `body.previous_sql` to `planner.plan()` | `backend/app/api/routes/analytics.py:49` | ✅ Already wired |
| `post_query()` passes `body.previous_sql` to `executor.generate_sql()` | `backend/app/api/routes/analytics.py:50` | ✅ Already wired |
| `AnalyticsExecutor.generate_sql()` uses `previous_sql` correctly | `backend/app/agents/analytics/executor.py:14-28` | ✅ Already implemented |
| `AnalyticsPlanner.plan()` accepts `previous_sql` parameter | `backend/app/agents/analytics/planner.py:16` | ✅ Accepts it |
| `AnalyticsPlanner.plan()` **ignores** `previous_sql` in messages | `backend/app/agents/analytics/planner.py:16-23` | ❌ **THE GAP — fix this** |

**The single backend gap:** `planner.plan()` accepts `previous_sql` but only puts `question` in the user message. The executor already does this correctly. Align the planner.

### Task 1: Fix `AnalyticsPlanner.plan()`

Current (broken — ignores `previous_sql`):
```python
async def plan(self, question: str, previous_sql: str | None = None) -> str:
    system_prompt = load_prompt("analytics_system")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},          # ← previous_sql ignored
    ]
    return await self._client.call(model=_MODEL, messages=messages, temperature=0.0)
```

Fixed (mirrors the executor pattern):
```python
async def plan(self, question: str, previous_sql: str | None = None) -> str:
    system_prompt = load_prompt("analytics_system")
    user_content = question
    if previous_sql:
        user_content = f"Previous SQL:\n{previous_sql}\n\nNew question:\n{question}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return await self._client.call(model=_MODEL, messages=messages, temperature=0.0)
```

**No prompt file changes needed.** `analytics_system.txt` already provides the shipments schema and context — the planner model will understand the SQL context from the message.

### Task 2: `useAnalytics.ts` — Full Implementation

`frontend/src/hooks/useAnalytics.ts` is currently a stub (`return {};`). Implement it:

```typescript
"use client";

import { useState } from "react";
import api from "@/lib/api";
import type { AnalyticsQueryResponse } from "@/types/api";

export function useAnalytics() {
  const [isQuerying, setIsQuerying] = useState(false);
  const [result, setResult] = useState<AnalyticsQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previousSql, setPreviousSql] = useState<string | null>(null);

  async function query(question: string) {
    setIsQuerying(true);
    setError(null);
    try {
      const response = await api.post<AnalyticsQueryResponse>("/query", {
        question,
        previous_sql: previousSql,   // null on first query; prior SQL on follow-up
      });
      setResult(response.data);
      // Store sql for next follow-up — AC1: previous_sql is the sole context source (AC3)
      if (response.data.sql) {
        setPreviousSql(response.data.sql);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred";
      setError(message);
    } finally {
      setIsQuerying(false);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
    setPreviousSql(null);   // AC3: no server-side state — clearing client state is a full reset
    setIsQuerying(false);
  }

  return { isQuerying, result, error, previousSql, query, reset };
}
```

**Key points:**
- `previousSql` starts as `null` — first query is always fresh (AC2)
- After each successful query, `result.sql` is stored as `previousSql` for the next call (AC1)
- `reset()` clears `previousSql` — caller uses this for "new conversation" button (AC3)
- `isQuerying` is the loading boolean — do NOT rename to `isLoading` (architecture pattern)
- API route is `/query` (axios `baseURL` already points to `/api` — check `frontend/src/lib/api.ts`)
- `previous_sql: previousSql` is sent as `null` on the first query — backend handles `null` gracefully (AC2)

**Check `lib/api.ts` baseURL:** The axios instance in `frontend/src/lib/api.ts` should have `baseURL: process.env.NEXT_PUBLIC_BACKEND_URL + "/api"`. Confirm before using `/query` vs `/api/query`.

### Testing pattern — `backend/tests/test_story_2_4.py`

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.agents.analytics.planner import AnalyticsPlanner
from app.services.model_client import ModelClient


class TestAnalyticsPlannerPreviousSql:
    def _make_client(self, return_value: str = "refined question") -> ModelClient:
        client = MagicMock(spec=ModelClient)
        client.call = AsyncMock(return_value=return_value)
        return client

    @pytest.mark.asyncio
    async def test_plan_with_previous_sql_includes_it_in_user_message(self):
        client = self._make_client()
        planner = AnalyticsPlanner(client)
        await planner.plan("Filter to Air only", previous_sql="SELECT * FROM shipments")
        call_kwargs = client.call.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        user_message = next(m["content"] for m in messages if m["role"] == "user")
        assert "SELECT * FROM shipments" in user_message
        assert "Filter to Air only" in user_message

    @pytest.mark.asyncio
    async def test_plan_without_previous_sql_sends_question_only(self):
        client = self._make_client()
        planner = AnalyticsPlanner(client)
        await planner.plan("What is total freight cost?", previous_sql=None)
        call_kwargs = client.call.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        user_message = next(m["content"] for m in messages if m["role"] == "user")
        assert user_message == "What is total freight cost?"

    @pytest.mark.asyncio
    async def test_plan_without_previous_sql_no_error(self):
        client = self._make_client("refined")
        planner = AnalyticsPlanner(client)
        result = await planner.plan("Any question")
        assert isinstance(result, str)


class TestPostQueryWithPreviousSql:
    def test_post_query_with_previous_sql_succeeds(self):
        from app.main import app
        client = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner, \
             patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor, \
             patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier, \
             patch("app.api.routes.analytics._generate_answer",
                   new=AsyncMock(return_value="Air shipments cost more")), \
             patch("app.api.routes.analytics._generate_follow_ups",
                   new=AsyncMock(return_value=[])):
            MockPlanner.return_value.classify_intent = AsyncMock(
                return_value={"intent": "answerable"}
            )
            MockPlanner.return_value.plan = AsyncMock(return_value="Filter to Air")
            MockExecutor.return_value.generate_sql = AsyncMock(
                return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments WHERE shipment_mode='Air' GROUP BY shipment_mode"
            )
            MockVerifier.return_value.verify = MagicMock(
                return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments WHERE shipment_mode='Air' GROUP BY shipment_mode"
            )
            resp = client.post(
                "/api/query",
                json={
                    "question": "Filter to Air only",
                    "previous_sql": "SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"] is None

    def test_post_query_without_previous_sql_succeeds(self):
        from app.main import app
        client = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner, \
             patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor, \
             patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier, \
             patch("app.api.routes.analytics._generate_answer",
                   new=AsyncMock(return_value="Here is the answer")), \
             patch("app.api.routes.analytics._generate_follow_ups",
                   new=AsyncMock(return_value=[])):
            MockPlanner.return_value.classify_intent = AsyncMock(
                return_value={"intent": "answerable"}
            )
            MockPlanner.return_value.plan = AsyncMock(return_value="fresh question")
            MockExecutor.return_value.generate_sql = AsyncMock(
                return_value="SELECT COUNT(*) FROM shipments"
            )
            MockVerifier.return_value.verify = MagicMock(
                return_value="SELECT COUNT(*) FROM shipments"
            )
            resp = client.post(
                "/api/query",
                json={"question": "How many shipments are there?"},
                # No previous_sql key at all
            )
        assert resp.status_code == 200
        assert resp.json()["error"] is None
```

### What NOT to Change

- `AnalyticsQueryRequest` — `previous_sql: str | None = None` already exists; do NOT add or rename
- `post_query()` — already passes `body.previous_sql` to both planner and executor; do NOT touch
- `AnalyticsExecutor.generate_sql()` — already correct; do NOT touch
- `AnalyticsVerifier` — no change
- Any prompt `.txt` files — `analytics_system.txt` already works for this context
- `backend/app/schemas/analytics.py` — no changes (Story 2.3 handles `ChartConfig` addition)

### Architecture: Stateless Context Design

The architecture decision is explicit:
> **Multi-turn context: stateless — client holds `previous_sql`**
> Context survives Render cold restarts; no server-side session state; aligns with REST principles.

This means:
- The backend has NO session table, NO in-memory dict, NO Redis — just reads from the request body
- The frontend (`useAnalytics.ts`) is the sole owner of conversation state
- `previousSql` is reset to `null` when user starts a new conversation
- Each request is self-contained — `previous_sql` is the complete context payload

### Request/Response Flow for Follow-up

```
User: "Filter that to Air shipments only"
  → useAnalytics.query("Filter that to Air only")
  → POST /api/query {
      "question": "Filter that to Air only",
      "previous_sql": "SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode"
    }
  → AnalyticsPlanner.plan(question, previous_sql)
      user_content = "Previous SQL:\n{sql}\n\nNew question:\nFilter that to Air only"
  → AnalyticsExecutor.generate_sql(refined_q, previous_sql)
      user_content = "Previous SQL:\n{sql}\n\nNew question:\n{refined_q}"
  → refined SQL: SELECT shipment_mode, AVG(...) FROM shipments WHERE shipment_mode='Air' GROUP BY shipment_mode
  → response.sql stored as next previousSql in useAnalytics hook
```

### Previous Story Learnings

From Story 2.3:
- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must appear **before any `app.*` import** in every test file.
- Route-level tests: patch `AnalyticsPlanner`, `AnalyticsExecutor`, `AnalyticsVerifier`, and all `_generate_*` helpers.
- `client.call.call_args` — use `.kwargs.get("messages") or .args[1]` pattern to extract the `messages` arg regardless of call style.

From Story 2.1:
- Test file naming: `backend/tests/test_story_2_4.py`
- All test classes use `class Test<Feature>:` pattern (no standalone functions).
- `AnalyticsVerifier.verify()` is synchronous (not async) — mock with `MagicMock`, not `AsyncMock`.

From Story 1.6:
- `ModelClient` is already correctly injected via `__init__` — use `MagicMock(spec=ModelClient)` in tests.

### References

- [Source: epics.md — Story 2.4]: Full AC text including FR5 reference
- [Source: architecture.md — Multi-turn context decision]: "Stateless — client sends `previous_sql` in request body"
- [Source: backend/app/agents/analytics/executor.py:14-28]: Executor `previous_sql` pattern to mirror in planner
- [Source: backend/app/agents/analytics/planner.py:16-23]: Current gap — plan() ignores previous_sql
- [Source: backend/app/api/routes/analytics.py:49-50]: Route already passes `body.previous_sql` to both
- [Source: frontend/src/hooks/useAnalytics.ts]: Stub — `return {};` — this story owns implementation

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — single backend gap (planner ignoring previous_sql) fixed cleanly.

### Completion Notes List

- Task 1: Fixed `planner.plan()` to prepend `"Previous SQL:\n{sql}\n\nNew question:\n{q}"` when `previous_sql` is provided. Mirrors executor pattern exactly.
- Task 2: Implemented `useAnalytics.ts` hook. Uses `/api/query` route (baseURL has no `/api` suffix). `previousSql` starts null, set from `response.data.sql` on each success, cleared on `reset()`.
- Task 3: 5 tests in `test_story_2_4.py`. All pass. 177 total tests, zero regressions.

### File List

Modified:
- `backend/app/agents/analytics/planner.py` — update `plan()` to include `previous_sql` in user message
- `frontend/src/hooks/useAnalytics.ts` — implement hook with `query()`, `reset()`, `previousSql` state

New:
- `backend/tests/test_story_2_4.py` — tests for planner context and route integration

## Change Log

- 2026-03-30: Story 2.4 created by create-story workflow
- 2026-03-30: Story 2.4 implemented, status → review
