# Story 2.2: Out-of-Scope Detection, NULL Surfacing, and Follow-Up Suggestions

Status: done

## Story

As a logistics analyst,
I want the system to tell me clearly when my question can't be answered from the data, report how many records were excluded due to NULL values, and suggest relevant follow-up questions,
So that I know the limits of the data and how to explore further.

## Acceptance Criteria

1. **Given** a user asks a question referencing data not in the dataset (e.g., "What is the carbon footprint of each shipment?")
   **When** the analytics pipeline processes the question
   **Then** the response `answer` explains what data is available and why the question can't be answered — no fabricated result is returned (FR6)

2. **Given** a query filters on a column containing NULL values (cleaned from `-49` sentinels during CSV load)
   **When** the response is constructed
   **Then** the `answer` text includes a sentence noting how many records were excluded due to NULL values in the relevant column (FR7)

3. **Given** a successful query completes
   **When** the response is returned
   **Then** it includes a `suggested_questions` array with 2–3 complete natural language follow-up questions relevant to the result (FR8)

## Tasks / Subtasks

- [x] Task 1: Extend `AnalyticsQueryResponse` schema (AC: 3)
  - [x] In `backend/app/schemas/analytics.py`, add `suggested_questions: list[str] = []` to `AnalyticsQueryResponse`
  - [x] No other schema changes — `answer`, `sql`, `columns`, `rows`, `row_count`, `error`, `message` fields remain unchanged

- [x] Task 2: Add prompt files for new LLM steps (AC: 1, 2, 3)
  - [x] Create `backend/app/prompts/analytics_planner.txt` — out-of-scope classification prompt (see Dev Notes for exact content)
  - [x] Create `backend/app/prompts/analytics_answer.txt` — answer generation prompt, moves the inline string from `_generate_answer()` (see Dev Notes)
  - [x] Create `backend/app/prompts/analytics_followup.txt` — follow-up question generation prompt (see Dev Notes for exact content)

- [x] Task 3: Add `classify_intent()` to `AnalyticsPlanner` (AC: 1)
  - [x] Add `async def classify_intent(self, question: str) -> dict` to `backend/app/agents/analytics/planner.py`
  - [x] Load `analytics_planner` prompt via `load_prompt("analytics_planner")`
  - [x] Call `ModelClient` with `model="meta-llama/llama-3.3-70b-instruct"`, `temperature=0.0`
  - [x] Parse LLM response as JSON: `{"intent": "answerable"}` or `{"intent": "out_of_scope", "answer": "..."}`
  - [x] On JSON parse failure: fall back to `{"intent": "answerable"}` and log a warning — never crash the pipeline
  - [x] Keep existing `plan()` method unchanged

- [x] Task 4: Add NULL exclusion counting to route (AC: 2)
  - [x] Add `_count_null_exclusions(db: Session, sql: str) -> dict[str, int]` helper in `backend/app/api/routes/analytics.py`
  - [x] Detect columns with `IS NOT NULL` in the SQL via regex: `re.findall(r'(\w+)\s+IS\s+NOT\s+NULL', sql, re.IGNORECASE)`
  - [x] For each detected column: run `SELECT COUNT(*) FROM shipments WHERE {col} IS NULL` to get excluded count
  - [x] Return `{"freight_cost_usd": 245, "weight_kg": 12, ...}` — only columns with count > 0 included
  - [x] Call this helper in `post_query()` after SQL execution (before `_generate_answer`)

- [x] Task 5: Update `_generate_answer()` to use prompt file and include NULL context (AC: 2)
  - [x] Replace inline system prompt in `_generate_answer()` with `load_prompt("analytics_answer")`
  - [x] Add `null_exclusions: dict[str, int]` parameter to `_generate_answer()`
  - [x] Pass null exclusion data in the user message context so the LLM incorporates it in the answer text

- [x] Task 6: Add follow-up suggestion generation to route (AC: 3)
  - [x] Add `async def _generate_follow_ups(client: ModelClient, question: str, answer: str, columns: list[str]) -> list[str]` in `backend/app/api/routes/analytics.py`
  - [x] Load `analytics_followup` prompt via `load_prompt("analytics_followup")`
  - [x] Call `ModelClient` with context: question + answer summary + column names
  - [x] Parse LLM response as JSON array; on parse failure return `[]` — never crash (graceful degradation)
  - [x] Return list of 2–3 strings

- [x] Task 7: Wire everything in `post_query()` route handler (AC: 1, 2, 3)
  - [x] Call `planner.classify_intent(body.question)` BEFORE `planner.plan()` and `executor.generate_sql()`
  - [x] If `intent["intent"] == "out_of_scope"`: return early with `AnalyticsQueryResponse(answer=intent["answer"], sql="", columns=[], rows=[], row_count=0, suggested_questions=[])`
  - [x] After DB execution, call `_count_null_exclusions(db, safe_sql)` → `null_exclusions`
  - [x] Pass `null_exclusions` to `_generate_answer()`
  - [x] After answer generation, call `_generate_follow_ups(client, body.question, answer, columns)` → `suggested_questions`
  - [x] Return `AnalyticsQueryResponse(..., suggested_questions=suggested_questions)`
  - [x] Error return paths (unsafe_sql, query_failed): keep `suggested_questions=[]`

- [x] Task 8: Write tests (AC: 1, 2, 3)
  - [x] Create `backend/tests/test_story_2_2.py`
  - [x] Test: `classify_intent` returns `{"intent": "out_of_scope", "answer": "..."}` when LLM returns out-of-scope JSON
  - [x] Test: `classify_intent` returns `{"intent": "answerable"}` when LLM returns answerable JSON
  - [x] Test: `classify_intent` falls back to `{"intent": "answerable"}` on JSON parse failure
  - [x] Test: `POST /api/query` with mocked out-of-scope intent returns non-empty `answer` with empty `sql`, `columns=[]`, `rows=[]`
  - [x] Test: `POST /api/query` successful response includes `suggested_questions` as a list
  - [x] Test: `_count_null_exclusions` returns correct counts for columns with IS NOT NULL in SQL
  - [x] Test: `_count_null_exclusions` returns empty dict when SQL has no IS NOT NULL clause
  - [x] Test: `_generate_follow_ups` returns empty list on JSON parse failure (graceful degradation)
  - [x] Test: `AnalyticsQueryResponse` schema includes `suggested_questions` field with default `[]`

## Dev Notes

### Architecture context

This story enhances the existing pipeline from Story 2.1. The Planner gains a pre-classification step.
All changes are additions/extensions — the Verifier and Executor are **not modified**.

```
POST /api/query
    │
    ├─► planner.classify_intent(question)      ← NEW (AC1)
    │       └─► if out_of_scope: return early  ← NEW
    │
    ├─► planner.plan(question, previous_sql)   ← UNCHANGED
    ├─► executor.generate_sql(...)             ← UNCHANGED
    ├─► verifier.verify(sql)                   ← UNCHANGED
    ├─► db.execute(text(sql))                  ← UNCHANGED
    ├─► _count_null_exclusions(db, sql)        ← NEW (AC2)
    ├─► _generate_answer(... null_exclusions)  ← MODIFIED (prompt file + null context)
    └─► _generate_follow_ups(...)              ← NEW (AC3)
```

### Schema — `app/schemas/analytics.py`

Add one field — everything else is untouched:

```python
class AnalyticsQueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    error: str | None = None
    message: str | None = None
    suggested_questions: list[str] = []   # NEW — empty on error or out-of-scope
```

### Prompt content — `analytics_planner.txt`

```
Classify whether the following user question can be answered from a supply chain shipments dataset.

The dataset contains freight shipments data with these fields:
country, shipment_mode (Air, Ocean, Truck, Air Charter), product_group (ARV, HRDT, ANTM, ACT, MRDT),
vendor, delivery dates, freight_cost_usd, weight_kg, line_item_quantity, line_item_value.

Questions about carbon footprint, emissions, temperatures, product formulas, customer names,
financial forecasts, or any data not listed above are out of scope.

Respond with ONLY valid JSON — no markdown, no explanation, no code fences:
If answerable: {"intent": "answerable"}
If out of scope: {"intent": "out_of_scope", "answer": "<1-2 sentences explaining what data IS available and why this question cannot be answered>"}
```

### Prompt content — `analytics_answer.txt`

This replaces the inline system prompt in `_generate_answer()` — same meaning, now from a file:

```
You are a freight analytics assistant for a USAID supply chain dataset.
Given a question, its SQL query, result rows, and any NULL exclusion counts,
write a concise 1-3 sentence natural language answer.
Be specific — include numbers from the results.
If NULL exclusions are provided, include one sentence noting how many records were excluded and from which column.
```

### Prompt content — `analytics_followup.txt`

```
Given a freight analytics question and its answer, suggest 2-3 relevant follow-up questions that explore the data further.

Focus on: drilling down by dimension (country, mode, vendor), comparing time periods, identifying outliers or top/bottom performers, or exploring related metrics.

Respond with ONLY a valid JSON array of strings — no markdown, no code fences:
["follow-up question 1", "follow-up question 2", "follow-up question 3"]
```

### Planner addition — `app/agents/analytics/planner.py`

Add `classify_intent()` below the existing `plan()` method. Do NOT modify `plan()`.

```python
import json
import logging

logger = logging.getLogger(__name__)

class AnalyticsPlanner:
    # ... existing __init__ and plan() unchanged ...

    async def classify_intent(self, question: str) -> dict:
        """Classify question as answerable or out_of_scope.

        Returns {"intent": "answerable"} or {"intent": "out_of_scope", "answer": "..."}.
        Falls back to {"intent": "answerable"} on any JSON parse failure.
        """
        planner_prompt = load_prompt("analytics_planner")
        messages = [
            {"role": "system", "content": planner_prompt},
            {"role": "user", "content": question},
        ]
        raw = await self._client.call(model=_MODEL, messages=messages, temperature=0.0)
        try:
            return json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            logger.warning("classify_intent JSON parse failed, defaulting to answerable: %s", raw[:100])
            return {"intent": "answerable"}
```

### NULL exclusion helper — `app/api/routes/analytics.py`

Add below `_generate_answer()`:

```python
import re

_NULL_COL_RE = re.compile(r"(\w+)\s+IS\s+NOT\s+NULL", re.IGNORECASE)


def _count_null_exclusions(db: Session, sql: str) -> dict[str, int]:
    """Count rows excluded by IS NOT NULL filters in the given SQL.

    Returns {column_name: excluded_count} for columns with excluded_count > 0.
    Only queries the shipments table — safe for analytics-layer use.
    """
    cols = list(dict.fromkeys(_NULL_COL_RE.findall(sql)))  # preserves order, deduplicates
    counts: dict[str, int] = {}
    for col in cols:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM shipments WHERE {col} IS NULL"))
            n = result.scalar() or 0
            if n > 0:
                counts[col] = n
        except Exception:
            pass  # unknown column or DB error — skip silently
    return counts
```

> **Security note:** `col` comes from parsing the LLM-generated SQL (not from user input), and only columns matching `\w+` (word chars only — no injection vectors) are extracted. This is safe.

### `_generate_answer()` update

```python
async def _generate_answer(
    client: ModelClient,
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list],
    null_exclusions: dict[str, int],   # NEW parameter
) -> str:
    preview_rows = rows[:_MAX_ROWS_IN_ANSWER_CONTEXT]
    null_info = (
        ", ".join(f"{n} records with NULL {col}" for col, n in null_exclusions.items())
        if null_exclusions else "none"
    )
    context = (
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Columns: {columns}\n"
        f"Rows (first {len(preview_rows)} of {len(rows)}): {preview_rows}\n"
        f"NULL exclusions: {null_info}"
    )
    messages = [
        {"role": "system", "content": load_prompt("analytics_answer")},
        {"role": "user", "content": context},
    ]
    return await client.call(model=_MODEL, messages=messages, temperature=0.0)
```

### `_generate_follow_ups()` helper

```python
async def _generate_follow_ups(
    client: ModelClient,
    question: str,
    answer: str,
    columns: list[str],
) -> list[str]:
    context = f"Question: {question}\nAnswer: {answer}\nResult columns: {columns}"
    messages = [
        {"role": "system", "content": load_prompt("analytics_followup")},
        {"role": "user", "content": context},
    ]
    raw = await client.call(model=_MODEL, messages=messages, temperature=0.7)
    try:
        suggestions = json.loads(raw.strip())
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions[:3]]
    except (json.JSONDecodeError, ValueError):
        logger.warning("_generate_follow_ups JSON parse failed: %s", raw[:100])
    return []
```

### Updated `post_query()` skeleton

```python
@router.post("/query", response_model=AnalyticsQueryResponse)
async def post_query(body: AnalyticsQueryRequest, db: Session = Depends(get_db)):
    client = ModelClient()
    planner = AnalyticsPlanner(client)
    executor = AnalyticsExecutor(client)
    verifier = AnalyticsVerifier()

    try:
        # AC1: out-of-scope check before any SQL generation
        intent = await planner.classify_intent(body.question)
        if intent.get("intent") == "out_of_scope":
            return AnalyticsQueryResponse(
                answer=intent.get("answer", "This question cannot be answered from the available data."),
                sql="", columns=[], rows=[], row_count=0,
            )

        refined_question = await planner.plan(body.question, body.previous_sql)
        sql = await executor.generate_sql(refined_question, body.previous_sql)
        safe_sql = verifier.verify(sql)

        result = db.execute(text(safe_sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
        row_count = len(rows)

        # AC2: NULL surfacing
        null_exclusions = _count_null_exclusions(db, safe_sql)

        # Generate answer with NULL context
        answer = await _generate_answer(client, body.question, safe_sql, columns, rows, null_exclusions)

        # AC3: follow-up suggestions
        suggested_questions = await _generate_follow_ups(client, body.question, answer, columns)

        return AnalyticsQueryResponse(
            answer=answer, sql=safe_sql, columns=columns,
            rows=rows, row_count=row_count,
            suggested_questions=suggested_questions,
        )

    except ValueError as e:
        logger.warning("Analytics verifier rejected SQL", extra={"error": str(e)})
        return AnalyticsQueryResponse(
            answer="", sql="", columns=[], rows=[], row_count=0,
            error="unsafe_sql", message=str(e),
        )
    except Exception as e:
        logger.exception("Analytics query failed")
        return AnalyticsQueryResponse(
            answer="", sql="", columns=[], rows=[], row_count=0,
            error="query_failed", message=str(e),
        )
```

### Testing pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.agents.analytics.planner import AnalyticsPlanner
from app.api.routes.analytics import _count_null_exclusions, _generate_follow_ups


class TestClassifyIntent:
    def _make_planner(self, mock_response: str) -> AnalyticsPlanner:
        client = MagicMock()
        client.call = AsyncMock(return_value=mock_response)
        return AnalyticsPlanner(client)

    @pytest.mark.asyncio
    async def test_out_of_scope_returns_correct_intent(self):
        raw = '{"intent": "out_of_scope", "answer": "Carbon footprint data is not available."}'
        planner = self._make_planner(raw)
        result = await planner.classify_intent("What is the carbon footprint?")
        assert result["intent"] == "out_of_scope"
        assert "carbon" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_answerable_returns_correct_intent(self):
        planner = self._make_planner('{"intent": "answerable"}')
        result = await planner.classify_intent("What is the average freight cost?")
        assert result["intent"] == "answerable"

    @pytest.mark.asyncio
    async def test_json_parse_failure_falls_back_to_answerable(self):
        planner = self._make_planner("I cannot determine this.")
        result = await planner.classify_intent("What is the average freight cost?")
        assert result["intent"] == "answerable"


class TestCountNullExclusions:
    def test_no_is_not_null_returns_empty(self):
        db = MagicMock()
        result = _count_null_exclusions(db, "SELECT COUNT(*) FROM shipments")
        assert result == {}
        db.execute.assert_not_called()

    def test_detects_is_not_null_and_counts(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 245
        db.execute.return_value = mock_result
        sql = "SELECT AVG(freight_cost_usd) FROM shipments WHERE freight_cost_usd IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert counts == {"freight_cost_usd": 245}

    def test_zero_count_excluded_from_result(self):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute.return_value = mock_result
        sql = "SELECT AVG(weight_kg) FROM shipments WHERE weight_kg IS NOT NULL"
        counts = _count_null_exclusions(db, sql)
        assert counts == {}


class TestGenerateFollowUps:
    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self):
        client = MagicMock()
        raw = '["How does this vary by country?", "What about Air shipments only?", "Show top 5 vendors."]'
        client.call = AsyncMock(return_value=raw)
        result = await _generate_follow_ups(client, "question", "answer", ["col1"])
        assert isinstance(result, list)
        assert len(result) <= 3
        assert all(isinstance(s, str) for s in result)

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_empty_list(self):
        client = MagicMock()
        client.call = AsyncMock(return_value="I cannot generate suggestions.")
        result = await _generate_follow_ups(client, "q", "a", [])
        assert result == []


class TestRouteOutOfScope:
    def test_out_of_scope_question_returns_answer_no_sql(self):
        from app.main import app
        client = TestClient(app)
        out_of_scope_json = '{"intent": "out_of_scope", "answer": "Carbon footprint data is not in the dataset."}'
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner:
            instance = MockPlanner.return_value
            instance.classify_intent = AsyncMock(
                return_value={"intent": "out_of_scope", "answer": "Carbon footprint data is not in the dataset."}
            )
            resp = client.post("/api/query", json={"question": "What is the carbon footprint?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["sql"] == ""
        assert body["columns"] == []
        assert body["rows"] == []
        assert "carbon" in body["answer"].lower() or len(body["answer"]) > 0

    def test_successful_response_includes_suggested_questions(self):
        from app.main import app
        client = TestClient(app)
        # ... mock full pipeline, assert suggested_questions is a list in response
        # See full test in test file
        pass
```

### What NOT to change
- `AnalyticsExecutor` — no modifications needed
- `AnalyticsVerifier` — no modifications needed
- `analytics_system.txt` — no modifications needed (Story 2.1 set the full content)
- `analytics_sql_gen.txt` — no modifications needed
- `main.py` — no modifications needed
- Any other route files

### Previous story learnings (Story 2.1)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` before any `app.*` import in every test file.
- Use `patch("app.api.routes.analytics.AnalyticsPlanner")` to mock — patch at the point of use, not the point of definition.
- `ModelClient` constructor uses settings eagerly — always mock `client.call` at the AsyncMock level, not the constructor.
- `TestClient` creates a new event loop — `AsyncMock` works correctly for async route handlers.
- For DB tests: the test infrastructure uses `StaticPool` — `_count_null_exclusions` will work against in-memory test DB (ships no data, so counts will be 0 — mock the DB execute call in unit tests).
- `json.loads(raw.strip())` — always `.strip()` the LLM response before parsing; LLMs often add trailing newlines.

### New file list for this story

- `backend/app/schemas/analytics.py` — modified: add `suggested_questions` field
- `backend/app/agents/analytics/planner.py` — modified: add `classify_intent()` method
- `backend/app/api/routes/analytics.py` — modified: wire out-of-scope check, NULL counting, follow-up generation; move inline prompt to file
- `backend/app/prompts/analytics_planner.txt` — new
- `backend/app/prompts/analytics_answer.txt` — new (moves inline prompt from route)
- `backend/app/prompts/analytics_followup.txt` — new
- `backend/tests/test_story_2_2.py` — new

### References

- [Source: epics.md — Story 2.2, line 430]: Full acceptance criteria text
- [Source: epics.md — Epic 2 FRs]: FR6 (out-of-scope detection), FR7 (NULL surfacing), FR8 (follow-up suggestions)
- [Source: architecture.md — Service boundaries, line 708]: Planner → Executor → Verifier flow diagram
- [Source: architecture.md — Enforcement, line 548]: All agents MUST route LLM calls through ModelClient
- [Source: story 2-1]: Planner.plan() is a passthrough — intent classification explicitly deferred to this story
- [Source: story 2-1 completion notes]: answer generated via `_generate_answer()` helper with inline system prompt — move to `analytics_answer.txt`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Regression fix: Story 2.1 `TestPostQueryRoute` tests used 3-item `side_effect` mock sequence; adding `classify_intent()` + `_generate_follow_ups()` changed the call sequence to 5 calls. Updated `_make_mock_client()` helper and two inline mocks to prepend `'{"intent": "answerable"}'` for classify_intent and append `'["Q1?", "Q2?"]'` for follow_ups.

### Completion Notes List

- Added `suggested_questions: list[str] = []` to `AnalyticsQueryResponse` schema — default empty, backward-compatible
- Created 3 new prompt files: `analytics_planner.txt` (JSON classification), `analytics_answer.txt` (moved inline prompt from route), `analytics_followup.txt` (JSON array follow-ups)
- Added `classify_intent()` to `AnalyticsPlanner` — loads `analytics_planner` prompt, parses JSON response, falls back to `{"intent": "answerable"}` on parse failure
- Added `_count_null_exclusions(db, sql)` in route — regex extracts IS NOT NULL columns, queries excluded row count per column, skips zeros and DB errors silently
- Updated `_generate_answer()` — inline prompt replaced with `load_prompt("analytics_answer")`, added `null_exclusions` param, null_info formatted into context string
- Added `_generate_follow_ups()` — calls LLM with context, parses JSON array, caps at 3 items, returns `[]` on parse failure
- Wired everything in `post_query()` — out-of-scope early return, null counting, follow-up generation all added
- 22 new tests in `test_story_2_2.py`; all 140 tests pass (22 new + 118 regression including updated 2.1 mocks)

### File List

- `backend/app/schemas/analytics.py` — modified: added `suggested_questions: list[str] = []` field
- `backend/app/agents/analytics/planner.py` — modified: added `classify_intent()` method, added `json`/`logging` imports
- `backend/app/api/routes/analytics.py` — modified: added `_count_null_exclusions()`, `_generate_follow_ups()`, updated `_generate_answer()`, wired all in `post_query()`; added `json`/`re` imports; added `load_prompt` import
- `backend/app/prompts/analytics_planner.txt` — new: out-of-scope classification prompt
- `backend/app/prompts/analytics_answer.txt` — new: answer generation prompt (replaces inline string)
- `backend/app/prompts/analytics_followup.txt` — new: follow-up suggestion prompt
- `backend/tests/test_story_2_2.py` — new: 22 tests covering all ACs
- `backend/tests/test_story_2_1.py` — modified: updated mock sequences to account for 2 new LLM calls in pipeline

### Review Findings

- [x] [Review][Decision] Unknown intent value silently proceeds to SQL — resolved as fail-closed: changed check to `intent.get("intent") != "answerable"` so any unexpected intent value triggers out-of-scope early return. [backend/app/api/routes/analytics.py:38]

- [x] [Review][Patch] Strip SQL comments before regex to prevent false-positive null counts — added `_SQL_LINE_COMMENT_RE` and `_SQL_BLOCK_COMMENT_RE`; strip before running `_NULL_COL_RE`. [backend/app/api/routes/analytics.py:22]

- [x] [Review][Patch] Add logging to silent exception swallow in `_count_null_exclusions` — replaced `except Exception: pass` with `logger.debug(...)`. [backend/app/api/routes/analytics.py:118]

- [x] [Review][Patch] Wrap `classify_intent` in separate try/except to prevent ValueError mis-routing — moved `classify_intent` call into its own `try/except Exception` block before the main pipeline try/except. [backend/app/api/routes/analytics.py:35]

- [x] [Review][Patch] Filter null/non-string items from `_generate_follow_ups` result — added `if s is not None and str(s).strip()` guard. [backend/app/api/routes/analytics.py:165]

- [x] [Review][Patch] Explicitly set `suggested_questions=[]` on error paths and out-of-scope return — added explicit `suggested_questions=[]` to all three return paths. [backend/app/api/routes/analytics.py:39,82,93]

- [x] [Review][Patch] Test: add test for `suggested_questions=[]` on `unsafe_sql` and `query_failed` error paths — added `TestRouteErrorPaths` class with 3 tests (unsafe_sql, query_failed, unknown_intent fail-closed). [backend/tests/test_story_2_2.py]

- [x] [Review][Patch] Test: add test verifying `_count_null_exclusions` is called from route when SQL has IS NOT NULL — added `TestNullExclusionsRouteWiring` class. [backend/tests/test_story_2_2.py]

- [x] [Review][Defer] `_count_null_exclusions` hardcodes `shipments` table — if LLM generates queries over joins or other tables, null counts are computed against `shipments` regardless; by design for the current single-table system. Address when multi-table queries are introduced (Epic 4). [backend/app/api/routes/analytics.py:114] — deferred, by design

- [x] [Review][Defer] Prompt injection via raw user question — `body.question` inserted verbatim into every LLM message without sanitization; pre-existing from Story 2.1, not introduced here. [backend/app/api/routes/analytics.py] — deferred, pre-existing

- [x] [Review][Defer] `ModelClient` instantiated per-request — connection pool exhaustion under load; pre-existing from Story 2.1. [backend/app/api/routes/analytics.py:30] — deferred, pre-existing

- [x] [Review][Defer] `previous_sql` accepted without validation — arbitrary client string forwarded to LLM; pre-existing from Story 2.1. [backend/app/schemas/analytics.py] — deferred, pre-existing

- [x] [Review][Defer] `rows: list[list]` untyped inner list — non-serializable DB types (Decimal, datetime) cause silent coercion or 500; pre-existing schema from Story 2.1. — deferred, pre-existing

- [x] [Review][Defer] DB cursor not closed after `db.execute()` — result not explicitly closed; pre-existing from Story 2.1. [backend/app/api/routes/analytics.py:53] — deferred, pre-existing

- [x] [Review][Defer] Dirty session state after `fetchall` exception — if `result.fetchall()` raises, session state is indeterminate before `_count_null_exclusions` runs; SQLAlchemy session lifecycle hardening is Epic 5/6 scope. — deferred, Epic 5/6

## Change Log

- 2026-03-30: Implemented Story 2.2 — out-of-scope detection via `classify_intent()`, NULL surfacing via `_count_null_exclusions()`, follow-up suggestions via `_generate_follow_ups()`, schema extended with `suggested_questions`. 22 new tests; 140/140 passing.
