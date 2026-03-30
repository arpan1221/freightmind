# Story 2.3: Chart Configuration Generation

Status: done

## Story

As a logistics analyst,
I want the analytics response to include a chart configuration when the result is quantitative,
So that I can see a visual representation of the data without configuring a chart manually.

## Acceptance Criteria

1. **Given** a query returns quantitative results with a categorical dimension (e.g., cost by shipment mode)
   **When** the response is constructed
   **Then** it includes a `chart_config` object with `type` (one of `bar`, `line`, `pie`), `x_key`, and `y_key` (FR4)

2. **Given** the `chart_config` is passed to the frontend `ChartRenderer`
   **When** the chart component renders
   **Then** a bar, line, or pie chart is displayed using Recharts with the correct data mapping from `columns` and `rows`

3. **Given** a query returns non-quantitative results (e.g., a list of vendor names)
   **When** the response is constructed
   **Then** `chart_config` is `null` — no chart is rendered

## Tasks / Subtasks

- [x] Task 1: Add `ChartConfig` Pydantic model and `chart_config` field to backend schema (AC: 1, 3)
  - [x] In `backend/app/schemas/analytics.py`, add `ChartConfig` model above `AnalyticsQueryResponse`
  - [x] Add `chart_config: ChartConfig | None = None` field to `AnalyticsQueryResponse`
  - [x] Do NOT change any other fields — `columns`, `rows`, `suggested_questions`, `error`, `message` stay as-is

- [x] Task 2: Create `analytics_chart.txt` prompt (AC: 1, 3)
  - [x] Create `backend/app/prompts/analytics_chart.txt` — see Dev Notes for exact content

- [x] Task 3: Add `_generate_chart_config()` to route (AC: 1, 3)
  - [x] Add `async def _generate_chart_config(client, question, columns, rows) -> dict | None` in `backend/app/api/routes/analytics.py`
  - [x] Return `None` immediately if `rows` is empty or `columns` is empty
  - [x] Load `analytics_chart` prompt, call `ModelClient` with `temperature=0.0`
  - [x] Parse JSON response: `{"type": "bar"|"line"|"pie", "x_key": str, "y_key": str}` or `null`
  - [x] Validate: `type` must be one of `"bar"`, `"line"`, `"pie"`; `x_key` and `y_key` must be present
  - [x] On any JSON parse failure, validation failure, or exception: return `None` — never crash

- [x] Task 4: Wire `_generate_chart_config()` in `post_query()` (AC: 1, 3)
  - [x] Call `_generate_chart_config(client, body.question, columns, rows)` after `_generate_answer()` and before `_generate_follow_ups()`
  - [x] Pass `chart_config=chart_config` in the success return
  - [x] Out-of-scope early return: pass `chart_config=None`
  - [x] Both error paths (`unsafe_sql`, `query_failed`): pass `chart_config=None`

- [x] Task 5: Fix `frontend/src/types/api.ts` to match actual backend schema (AC: 2)
  - [x] Replace `data: Record<string, unknown>[]` with `columns: string[]` and `rows: unknown[][]`
  - [x] Rename `suggestions: string[]` to `suggested_questions: string[]`
  - [x] Remove `null_exclusions: number` (not in backend response schema)
  - [x] Add `message: string | null` (already in backend, missing in frontend type)
  - [x] `chart_config: ChartConfig | null` was already in the type — verify it remains
  - [x] `ChartConfig` interface was already in the type — verify it matches backend model

- [x] Task 6: Implement `ChartRenderer.tsx` (AC: 2, 3)
  - [x] Implement `frontend/src/components/ChartRenderer.tsx` — see Dev Notes for full implementation
  - [x] Accept props: `chartConfig: ChartConfig`, `columns: string[]`, `rows: unknown[][]`
  - [x] Internally convert `columns`/`rows` to Recharts-compatible object array
  - [x] Render `BarChart`, `LineChart`, or `PieChart` based on `chartConfig.type`
  - [x] Wrap all charts in `ResponsiveContainer width="100%" height={300}`

- [x] Task 7: Write tests (AC: 1, 2, 3)
  - [x] Create `backend/tests/test_story_2_3.py`
  - [x] Test: `_generate_chart_config` returns valid `ChartConfig`-compatible dict when LLM returns valid JSON
  - [x] Test: `_generate_chart_config` returns `None` when LLM returns JSON `null`
  - [x] Test: `_generate_chart_config` returns `None` on JSON parse failure
  - [x] Test: `_generate_chart_config` returns `None` when `rows=[]`
  - [x] Test: `_generate_chart_config` returns `None` when `columns=[]`
  - [x] Test: `POST /api/query` success response includes `chart_config` field (non-null for quantitative mocked result)
  - [x] Test: `POST /api/query` out-of-scope response includes `chart_config: null`
  - [x] Test: `AnalyticsQueryResponse` schema includes `chart_config` field defaulting to `None`
  - [x] Run all existing tests — zero regressions (168 passed)

## Dev Notes

### Architecture Context

Story 2.3 adds one new step to the pipeline, between answer generation and follow-up suggestions:

```
POST /api/query
    │
    ├─► planner.classify_intent(question)           ← Story 2.2
    │       └─► if out_of_scope: return early
    │
    ├─► planner.plan(question, previous_sql)        ← Story 2.1
    ├─► executor.generate_sql(...)                  ← Story 2.1
    ├─► verifier.verify(sql)                        ← Story 2.1
    ├─► db.execute(text(sql))                       ← Story 2.1
    ├─► _count_null_exclusions(db, sql)             ← Story 2.2
    ├─► _generate_answer(...)                       ← Story 2.2
    ├─► _generate_chart_config(...)                 ← NEW (AC1, AC3)
    └─► _generate_follow_ups(...)                   ← Story 2.2
```

**Only additions:** `ChartConfig` model, `chart_config` field, `_generate_chart_config()`, `analytics_chart.txt`.
**Planner, Executor, Verifier are NOT modified.**

### Critical: Frontend Types Reconciliation

`frontend/src/types/api.ts` was created in Story 1.7 based on the architecture document but does not match the actual backend implementation from Stories 2.1/2.2. **This story must fix the mismatch before implementing ChartRenderer** — otherwise Story 2.6 will have to fix it later under time pressure.

| Field | Frontend type (current — WRONG) | Backend schema (actual) | Fix |
|-------|----------------------------------|--------------------------|-----|
| result data | `data: Record<string, unknown>[]` | `columns: string[]` + `rows: list[list]` | Replace `data` with `columns: string[]` and `rows: unknown[][]` |
| follow-ups | `suggestions: string[]` | `suggested_questions: list[str] = []` | Rename `suggestions` → `suggested_questions` |
| null info | `null_exclusions: number` | Not in response schema | Remove |
| error context | missing `message` | `message: str | None = None` | Add `message: string \| null` |
| chart | `chart_config: ChartConfig \| null` | Not yet (this story adds it) | Keep — this story adds it to backend |

Corrected `AnalyticsQueryResponse` interface:

```typescript
export interface AnalyticsQueryResponse {
  answer: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  chart_config: ChartConfig | null;
  suggested_questions: string[];
  error: string | null;
  message: string | null;
}
```

`ChartConfig` interface was already correct in the type file — no change needed:
```typescript
export interface ChartConfig {
  type: "bar" | "line" | "pie";
  x_key: string;
  y_key: string;
}
```

### Backend: Schema Update — `app/schemas/analytics.py`

Add `ChartConfig` above `AnalyticsQueryResponse`, then add the field:

```python
from pydantic import BaseModel


class ChartConfig(BaseModel):
    type: str  # "bar" | "line" | "pie"
    x_key: str
    y_key: str


class AnalyticsQueryRequest(BaseModel):
    question: str
    previous_sql: str | None = None


class AnalyticsQueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    chart_config: ChartConfig | None = None   # NEW
    error: str | None = None
    message: str | None = None
    suggested_questions: list[str] = []
```

### Backend: Prompt — `analytics_chart.txt`

```
Given a data analytics question and its SQL result (column names and sample rows), determine whether a chart is appropriate and what configuration to use.

Rules:
- Return null if the result has only 1 row (single scalar — no chart needed)
- Return null if no numeric column is present (cannot chart text-only results)
- Return null if the result has more than 1 numeric column and no clear primary metric
- Use "bar" for categorical comparisons (e.g., total cost by shipment mode, count by country)
- Use "line" for time series where the x dimension is ordered by date or time period
- Use "pie" for distributions with 2–6 distinct categories showing proportions of a whole

x_key: the categorical or time dimension column name (axis labels)
y_key: the primary numeric metric column name (values being measured)

Respond with ONLY valid JSON — no markdown, no explanation, no code fences:
If chart appropriate: {"type": "bar"|"line"|"pie", "x_key": "<exact_column_name>", "y_key": "<exact_column_name>"}
If no chart appropriate: null
```

### Backend: `_generate_chart_config()` — `app/api/routes/analytics.py`

Add after `_generate_follow_ups()`:

```python
async def _generate_chart_config(
    client: ModelClient,
    question: str,
    columns: list[str],
    rows: list[list],
) -> dict | None:
    """Generate chart configuration for quantitative results.

    Returns {"type": "bar"|"line"|"pie", "x_key": str, "y_key": str} or None.
    Returns None (not null) on empty data, JSON parse failure, or invalid structure.
    """
    if not rows or not columns:
        return None

    preview_rows = rows[:5]
    context = (
        f"Question: {question}\n"
        f"Result columns: {columns}\n"
        f"Sample rows (first {len(preview_rows)} of {len(rows)}): {preview_rows}"
    )
    messages = [
        {"role": "system", "content": load_prompt("analytics_chart")},
        {"role": "user", "content": context},
    ]
    try:
        raw = await client.call(model=_MODEL, messages=messages, temperature=0.0)
        result = json.loads(raw.strip())
        if result is None:
            return None
        if (
            isinstance(result, dict)
            and result.get("type") in ("bar", "line", "pie")
            and isinstance(result.get("x_key"), str)
            and isinstance(result.get("y_key"), str)
        ):
            return result
        logger.warning("_generate_chart_config invalid structure: %s", result)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_generate_chart_config JSON parse failed: %s", raw[:100] if 'raw' in dir() else "")
    except Exception:
        logger.exception("_generate_chart_config unexpected error")
    return None
```

### Backend: `post_query()` Updated Skeleton

Add the `_generate_chart_config` call between answer and follow-ups:

```python
answer = await _generate_answer(client, body.question, safe_sql, columns, rows, null_exclusions)

# AC1 / AC3: chart config generation
chart_config = await _generate_chart_config(client, body.question, columns, rows)

suggested_questions = await _generate_follow_ups(client, body.question, answer, columns)

return AnalyticsQueryResponse(
    answer=answer,
    sql=safe_sql,
    columns=columns,
    rows=rows,
    row_count=row_count,
    chart_config=chart_config,
    suggested_questions=suggested_questions,
)
```

Also update the `ChartConfig` import from `app.schemas.analytics`:

```python
from app.schemas.analytics import AnalyticsQueryRequest, AnalyticsQueryResponse, ChartConfig
```

**Note:** `chart_config=None` must be passed in all early-return paths (out-of-scope, unsafe_sql, query_failed). All three already use `AnalyticsQueryResponse(...)` — just add `chart_config=None` to each.

### Frontend: `ChartRenderer.tsx` — Recharts 3.8.1

Recharts 3.x installs are at `^3.8.1`. The core API (`BarChart`, `LineChart`, `PieChart`, `ResponsiveContainer`, `XAxis`, `YAxis`, `Bar`, `Line`, `Pie`, `Cell`, `CartesianGrid`, `Tooltip`, `Legend`) is stable.

**Props:** `chartConfig: ChartConfig`, `columns: string[]`, `rows: unknown[][]`

```typescript
"use client";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartConfig } from "@/types/api";

interface ChartRendererProps {
  chartConfig: ChartConfig;
  columns: string[];
  rows: unknown[][];
}

const CHART_COLORS = [
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#0891b2",
];

export default function ChartRenderer({ chartConfig, columns, rows }: ChartRendererProps) {
  // Convert columns/rows (backend format) → Recharts object array
  const data = rows.map((row) =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]]))
  );

  const { type, x_key, y_key } = chartConfig;

  if (type === "bar") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={x_key} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey={y_key} fill={CHART_COLORS[0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (type === "line") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={x_key} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey={y_key} stroke={CHART_COLORS[0]} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            nameKey={x_key}
            dataKey={y_key}
            cx="50%"
            cy="50%"
            outerRadius={100}
            label
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  return null;
}
```

**Note on `"use client"`:** `ChartRenderer` uses Recharts (browser-only DOM rendering). It must remain a Client Component.

### Testing Pattern — `backend/tests/test_story_2_3.py`

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.api.routes.analytics import _generate_chart_config
from app.schemas.analytics import AnalyticsQueryResponse


class TestGenerateChartConfig:
    def _make_client(self, raw: str) -> MagicMock:
        client = MagicMock()
        client.call = AsyncMock(return_value=raw)
        return client

    @pytest.mark.asyncio
    async def test_returns_valid_chart_config(self):
        raw = '{"type": "bar", "x_key": "shipment_mode", "y_key": "avg_cost"}'
        client = self._make_client(raw)
        result = await _generate_chart_config(client, "question", ["shipment_mode", "avg_cost"], [["Air", 1200]])
        assert result == {"type": "bar", "x_key": "shipment_mode", "y_key": "avg_cost"}

    @pytest.mark.asyncio
    async def test_returns_none_for_json_null(self):
        client = self._make_client("null")
        result = await _generate_chart_config(client, "q", ["vendor"], [["ABC"]])
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_parse_failure(self):
        client = self._make_client("I cannot determine chart type.")
        result = await _generate_chart_config(client, "q", ["col"], [["v"]])
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_rows(self):
        client = MagicMock()
        result = await _generate_chart_config(client, "q", ["col"], [])
        client.call.assert_not_called()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_columns(self):
        client = MagicMock()
        result = await _generate_chart_config(client, "q", [], [["v"]])
        client.call.assert_not_called()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_type(self):
        raw = '{"type": "scatter", "x_key": "a", "y_key": "b"}'
        client = self._make_client(raw)
        result = await _generate_chart_config(client, "q", ["a", "b"], [["x", 1]])
        assert result is None


class TestSchemaChartConfig:
    def test_response_has_chart_config_defaulting_to_none(self):
        resp = AnalyticsQueryResponse(
            answer="", sql="", columns=[], rows=[], row_count=0
        )
        assert resp.chart_config is None

    def test_response_accepts_chart_config(self):
        from app.schemas.analytics import ChartConfig
        config = ChartConfig(type="bar", x_key="mode", y_key="cost")
        resp = AnalyticsQueryResponse(
            answer="a", sql="s", columns=["mode", "cost"], rows=[["Air", 100]], row_count=1,
            chart_config=config,
        )
        assert resp.chart_config.type == "bar"


class TestRouteChartConfig:
    def test_successful_response_includes_chart_config_field(self):
        from app.main import app
        from unittest.mock import patch
        client = TestClient(app)
        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner, \
             patch("app.api.routes.analytics.AnalyticsExecutor") as MockExecutor, \
             patch("app.api.routes.analytics.AnalyticsVerifier") as MockVerifier, \
             patch("app.api.routes.analytics._generate_answer", new=AsyncMock(return_value="answer")), \
             patch("app.api.routes.analytics._generate_chart_config", new=AsyncMock(
                 return_value={"type": "bar", "x_key": "mode", "y_key": "cost"}
             )), \
             patch("app.api.routes.analytics._generate_follow_ups", new=AsyncMock(return_value=[])):
            MockPlanner.return_value.classify_intent = AsyncMock(return_value={"intent": "answerable"})
            MockPlanner.return_value.plan = AsyncMock(return_value="refined")
            MockExecutor.return_value.generate_sql = AsyncMock(return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode")
            MockVerifier.return_value.verify = MagicMock(return_value="SELECT shipment_mode, AVG(freight_cost_usd) FROM shipments GROUP BY shipment_mode")
            resp = client.post("/api/query", json={"question": "avg cost by mode"})
        assert resp.status_code == 200
        body = resp.json()
        assert "chart_config" in body
```

### What NOT to Change

- `AnalyticsPlanner`, `AnalyticsExecutor`, `AnalyticsVerifier` — no modifications
- Any existing prompt files
- `main.py` — no modifications
- `_count_null_exclusions()` — no modifications
- `_generate_answer()` — no modifications
- `_generate_follow_ups()` — no modifications
- Other route files

### Previous Story Learnings (Stories 2.1 and 2.2)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must come **before any `app.*` import** in every test file.
- When patching route-level functions (like `_generate_answer`, `_generate_chart_config`), use `patch("app.api.routes.analytics._generate_chart_config", new=AsyncMock(...))`.
- Mock the full pipeline for route-level tests: patch `AnalyticsPlanner`, `AnalyticsExecutor`, `AnalyticsVerifier`, and all `_generate_*` helpers.
- The mock call sequence in `TestPostQueryRoute` in `test_story_2_1.py` was already broken once (Story 2.2 added 2 calls). Adding `_generate_chart_config` adds 1 more LLM call — **update `test_story_2_1.py` mock sequences** if they use positional `side_effect` lists.
- `json.loads(raw.strip())` — always `.strip()` before parsing.
- `_MODEL` constant is defined at the top of `analytics.py` route — reuse it in `_generate_chart_config`.
- `load_prompt("analytics_chart")` — prompt file name must exactly match filename without extension.

### File List

Modified:
- `backend/app/schemas/analytics.py` — add `ChartConfig` model, add `chart_config` field to `AnalyticsQueryResponse`
- `backend/app/api/routes/analytics.py` — add `_generate_chart_config()`, wire in `post_query()`, add `ChartConfig` import
- `backend/tests/test_story_2_1.py` — update mock sequences if `side_effect` lists are positional (add chart_config mock call)
- `frontend/src/types/api.ts` — fix `AnalyticsQueryResponse`: replace `data`→`columns`+`rows`, rename `suggestions`→`suggested_questions`, remove `null_exclusions`, add `message`
- `frontend/src/components/ChartRenderer.tsx` — implement Recharts bar/line/pie renderer

New:
- `backend/app/prompts/analytics_chart.txt` — chart config generation prompt
- `backend/tests/test_story_2_3.py` — tests for chart config generation

### References

- [Source: epics.md — Story 2.3]: Full acceptance criteria text
- [Source: epics.md — Epic 2 FR4]: `chart_config` with `{type, x_key, y_key}` in analytics response
- [Source: architecture.md — Frontend Architecture]: "Chart rendering — Recharts — driven by `chart_config` from backend; backend returns `{ type, x_key, y_key }`; frontend maps to Recharts component"
- [Source: architecture.md — Component Boundaries]: `ChartRenderer ◄── chart_config`
- [Source: architecture.md — JSON Field Naming]: `snake_case` throughout; `response.data.chart_config.x_key` — no camelCase conversion
- [Source: story 2-2]: Pipeline order, `_generate_answer()` / `_generate_follow_ups()` signatures, LLM call patterns
- [Source: story 1-7]: `ChartRenderer.tsx` stub is at `frontend/src/components/ChartRenderer.tsx`; `frontend/src/types/api.ts` has `ChartConfig` and `AnalyticsQueryResponse` stubs

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — all tasks implemented cleanly.

### Completion Notes List

- All 7 tasks completed. 168 tests pass, zero regressions.
- `_generate_chart_config` returns `ChartConfig` object (not dict) — tests updated to use attribute access.
- `test_story_2_1.py` mock side_effect updated from 5 to 6 items (added `'null'` for chart config call at index 4).

### File List

Modified:
- `backend/app/schemas/analytics.py`
- `backend/app/api/routes/analytics.py`
- `backend/tests/test_story_2_1.py`
- `frontend/src/types/api.ts`
- `frontend/src/components/ChartRenderer.tsx`

New:
- `backend/app/prompts/analytics_chart.txt`
- `backend/tests/test_story_2_3.py`

### Review Findings

- [x] [Review][Patch] `ChartConfig.type` should be `Literal["bar", "line", "pie"]` not `str` [`backend/app/schemas/analytics.py:6`]
- [x] [Review][Patch] Strip markdown code fences from LLM response before JSON parsing in `_generate_chart_config` [`backend/app/api/routes/analytics.py:238`]
- [x] [Review][Patch] Validate `x_key` and `y_key` are present in `columns` before returning `ChartConfig`; hallucinated column names cause silent empty charts [`backend/app/api/routes/analytics.py:244`]
- [x] [Review][Defer] Log truncation at 100 chars in `_generate_chart_config` warning — minor debug ergonomics, pre-existing pattern in codebase [`backend/app/api/routes/analytics.py:252`] — deferred, pre-existing
- [x] [Review][Defer] No test for LLM-hallucinated column names in `x_key`/`y_key` — integration/contract test concern, not actionable as unit test — deferred, pre-existing

## Change Log

- 2026-03-30: Story 2.3 created by create-story workflow
- 2026-03-30: Story 2.3 implemented, status → review
- 2026-03-30: Code review complete — 3 patch, 2 defer, 7 dismissed
