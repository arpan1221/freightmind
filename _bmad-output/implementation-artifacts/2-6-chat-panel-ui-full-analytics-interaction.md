# Story 2.6: Chat Panel UI — Full Analytics Interaction

Status: review

## Story

As a logistics analyst,
I want a chat panel in the frontend where I can type questions and see the AI's answer with the SQL used, a data table, a chart, and suggested follow-ups,
So that I have a complete self-service analytics interface.

## Acceptance Criteria

1. **Given** the user types a question and submits it
   **When** the request is in flight
   **Then** a loading spinner appears within 300ms of submission using an `isQuerying` boolean (NFR5, UX-DR7)

2. **Given** a successful response arrives
   **When** it is rendered
   **Then** the chat panel displays: the text answer, a collapsible SQL block (collapsed by default, expandable on click), a data table with column headers and row count, a chart (if `chart_config` is not null), and suggested follow-up question chips (UX-DR1, UX-DR6, FR2, FR3, FR4, FR8)

3. **Given** the user clicks a suggested follow-up chip
   **When** it is clicked
   **Then** the chip's text is submitted as the next question with `previous_sql` populated from the prior response

4. **Given** the user opens `http://localhost:3000`
   **When** the page loads
   **Then** a dataset status card shows table names and row counts sourced from `GET /api/schema` (UX-DR3)

## Tasks / Subtasks

- [x] Task 1: Add `SchemaInfoResponse` types to `src/types/api.ts` (AC: 4)
  - [x] Add `ColumnInfo`, `TableInfo`, and `SchemaInfoResponse` interfaces — see Dev Notes
  - [x] **Also fix the `AnalyticsQueryRequest` interface** — `previous_sql` is a top-level field, NOT nested under `context` — see Dev Notes for correct shape

- [x] Task 2: Implement `DatasetStatus.tsx` (AC: 4)
  - [x] Replace stub with component that calls `GET /api/schema` on mount via axios
  - [x] While loading: show a muted "Loading dataset…" text
  - [x] On success: render a card listing each `table_name` and its `row_count` in a compact row
  - [x] On error: render a muted "Schema unavailable" text — do NOT crash or show a toast (this is informational, not a blocking error)
  - [x] Use `isLoadingSchema` boolean state (not a shared `isLoading`)
  - [x] See Dev Notes for the `GET /api/schema` response shape

- [x] Task 3: Implement `SqlDisclosure.tsx` (AC: 2)
  - [x] Props: `sql: string`
  - [x] Renders a `<details>` element (collapsed by default — no JS needed, native HTML)
  - [x] `<summary>` label: "Show SQL"
  - [x] Body: `<pre><code>` block containing the SQL string
  - [x] Tailwind classes for monospace, light background, rounded border

- [x] Task 4: Implement `ResultTable.tsx` (AC: 2)
  - [x] Props: `columns: string[]`, `rows: unknown[][]`, `rowCount: number`
  - [x] Render a `<table>` with `<thead>` from `columns` and `<tbody>` from `rows`
  - [x] Show row count below the table: "Showing {rows.length} of {rowCount} rows" (backend caps at 200 rows)
  - [x] If `columns` is empty or `rows` is empty: render `<p>No results.</p>`
  - [x] Use `table-auto w-full text-sm` Tailwind classes; alternate row backgrounds with `even:bg-gray-50`

- [x] Task 5: Implement `useAnalytics.ts` hook (AC: 1, 2, 3)
  - [x] **Check if Story 2.4 was implemented first** — if `useAnalytics.ts` already has real state, extend it instead of replacing
  - [x] State: `messages: Message[]`, `isQuerying: boolean`, `error: string | null`
  - [x] `Message` type (local to hook or co-located): `{ role: "user" | "assistant"; text?: string; response?: AnalyticsQueryResponse }`
  - [x] Expose `query(question: string): Promise<void>` — appends user message, calls `POST /api/query`, appends assistant response
  - [x] `POST /api/query` request body: `{ question, previous_sql: <last response's sql or null> }` — `previous_sql` taken from the last assistant message's `response.sql`
  - [x] On success: set `result.sql` tracking for next follow-up; append assistant message
  - [x] On error (axios non-2xx or network failure): set `error` string; do NOT append broken assistant message
  - [x] Expose `reset(): void` — clears `messages`, `isQuerying`, and `error`
  - [x] Uses `isQuerying` boolean — not a shared `isLoading`

- [x] Task 6: Implement `ChatPanel.tsx` (AC: 1, 2, 3, 4)
  - [x] `"use client"` directive — this is an interactive component
  - [x] Import and use `useAnalytics` hook
  - [x] Render `<DatasetStatus />` at the top of the panel
  - [x] Message thread: scroll container mapping `messages` array; user messages right-aligned, assistant messages left-aligned
  - [x] For each assistant message with a response: render in this order:
    1. Answer text (`response.answer`)
    2. `<SqlDisclosure sql={response.sql} />` (only if `response.sql` is non-empty)
    3. `<ResultTable columns={response.columns} rows={response.rows} rowCount={response.row_count} />` (only if `response.columns.length > 0`)
    4. `<ChartRenderer chartConfig={response.chart_config} columns={response.columns} rows={response.rows} />` (only if `response.chart_config` is not null)
    5. Follow-up chips: one `<button>` per `response.suggested_questions` entry — clicking calls `query(chip.text)`
  - [x] Input area: `<textarea>` or `<input>` for question, "Ask" `<button>`, submit on Enter (not Shift+Enter)
  - [x] Disable input + show spinner when `isQuerying === true`
  - [x] If `error` is non-null: show a red error banner below the last message
  - [x] Auto-scroll to bottom after each new message

- [x] Task 7: Verify `pnpm build` passes with no TypeScript errors (AC: 1–4)
  - [x] Run `pnpm build` from `frontend/` — must complete with zero errors or type warnings

## Dev Notes

### What Already Exists — DO NOT Reinvent

| File | Status | Notes |
|------|--------|-------|
| `src/components/ChartRenderer.tsx` | ✅ **Fully implemented** | Takes `{ chartConfig: ChartConfig, columns: string[], rows: unknown[][] }`. Do NOT touch. |
| `src/components/ConfidenceBadge.tsx` | Stub | Not needed for this story — belongs to Story 3.7 |
| `src/components/UploadPanel.tsx` | Stub | Not needed for this story |
| `src/hooks/useExtraction.ts` | Stub | Not needed for this story |
| `src/lib/api.ts` | ✅ Implemented | `axios.create({ baseURL: process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000" })`. Import as `import api from "@/lib/api"`. |
| `src/types/api.ts` | Partial | Needs `SchemaInfoResponse` types added AND `AnalyticsQueryRequest` fix (see below) |
| `src/app/page.tsx` | ✅ Tab switcher | Renders `<ChatPanel />` on Analytics tab — no changes needed |
| `src/app/globals.css` | ✅ Tailwind v4 | Uses `@import "tailwindcss"` — no `tailwind.config.ts` exists, do not create one |

### CRITICAL: `AnalyticsQueryRequest` Type Mismatch

The current `types/api.ts` has `previous_sql` nested under `context`. This is **wrong** — the backend expects it as a top-level field.

**Current (wrong):**
```typescript
export interface AnalyticsQueryRequest {
  question: string;
  context?: { previous_sql?: string | null; filters?: Record<string, unknown> };
}
```

**Correct (match actual backend schema):**
```typescript
export interface AnalyticsQueryRequest {
  question: string;
  previous_sql?: string | null;
}
```

Fix this in Task 1. The `AnalyticsQueryResponse` shape is already correct — do not touch it.

### Actual Backend API Contracts

**`POST /api/query`**
```
Request:  { "question": "string (1–2000 chars)", "previous_sql": "string | null" }
Response: AnalyticsQueryResponse (see types/api.ts — already correct)
```

**`GET /api/schema`** (not yet in `types/api.ts` — add in Task 1)
```json
{
  "tables": [
    {
      "table_name": "shipments",
      "row_count": 10324,
      "columns": [
        { "column_name": "country", "sample_values": ["Nigeria", "Zambia", "Tanzania"] }
      ]
    }
  ]
}
```

TypeScript interfaces to add to `src/types/api.ts`:
```typescript
export interface ColumnInfo {
  column_name: string;
  sample_values: unknown[];
}

export interface TableInfo {
  table_name: string;
  row_count: number;
  columns: ColumnInfo[];
}

export interface SchemaInfoResponse {
  tables: TableInfo[];
}
```

### Story 2.4 Dependency

Story 2.4 (Stateless Follow-Up Query) is `ready-for-dev` and includes Task 2: implement `useAnalytics.ts`. **If Story 2.4 was completed before this story:**
- The hook already exists with `isQuerying`, `previousSql`, `query()`, `reset()` state
- Extend it to add `messages: Message[]` state tracking instead of replacing it
- The backend wiring (`AnalyticsPlanner.plan()` using `previous_sql`) is already done

**If implementing 2.6 before 2.4 (not recommended but possible):**
- Implement the full hook as described in Task 5 above
- Story 2.4's remaining work is only the backend `AnalyticsPlanner.plan()` fix

### `AnalyticsQueryResponse` — Confirmed Actual Shape

From `backend/app/schemas/analytics.py` (source of truth):
```python
class AnalyticsQueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list]            # max 200 rows (hard cap in route)
    row_count: int              # total DB count (may exceed 200)
    chart_config: ChartConfig | None = None
    error: str | None = None
    message: str | None = None
    suggested_questions: list[str] = []
```

The `types/api.ts` interface already matches this correctly (it uses `suggested_questions` not `suggestions`).

### Tailwind v4 Notes

- **No `tailwind.config.ts`** — Next.js 16 + Tailwind 4 uses CSS-native config
- Use standard utility classes directly: `text-sm`, `bg-gray-50`, `border`, `rounded`, etc.
- Confidence badge CSS vars are in `globals.css`: `--badge-high: #16a34a`, `--badge-medium: #d97706`, `--badge-low: #dc2626`
- For monospace code blocks use `font-mono` class

### Naming Conventions (from architecture.md)

| Convention | Rule | Example |
|------------|------|---------|
| Components | `PascalCase` file + export | `ChatPanel`, `SqlDisclosure` |
| Hooks | `use` + `PascalCase` | `useAnalytics` |
| Variables | `camelCase` | `previousSql`, `isQuerying` |
| API response fields | `snake_case` — no conversion | `response.data.chart_config.x_key` |
| Loading states | `is` + `PascalCase` verb | `isQuerying`, `isLoadingSchema` |
| Event handlers | `handle` + `PascalCase` noun | `handleSubmit`, `handleChipClick` |

### `DatasetStatus.tsx` — API Call Pattern

```typescript
"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import type { SchemaInfoResponse } from "@/types/api";

export default function DatasetStatus() {
  const [schema, setSchema] = useState<SchemaInfoResponse | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(true);

  useEffect(() => {
    api.get<SchemaInfoResponse>("/api/schema")
      .then(res => setSchema(res.data))
      .catch(() => setSchema(null))
      .finally(() => setIsLoadingSchema(false));
  }, []);

  if (isLoadingSchema) return <p className="text-sm text-gray-400">Loading dataset…</p>;
  if (!schema) return <p className="text-sm text-gray-400">Schema unavailable</p>;

  return (
    <div className="flex gap-4 text-sm text-gray-600 mb-2">
      {schema.tables.map(t => (
        <span key={t.table_name}><strong>{t.table_name}</strong>: {t.row_count.toLocaleString()} rows</span>
      ))}
    </div>
  );
}
```

### `SqlDisclosure.tsx` — Native HTML Pattern

Use `<details>`/`<summary>` — no JS state needed, no `useState`. This is intentional.

```typescript
interface SqlDisclosureProps { sql: string; }

export default function SqlDisclosure({ sql }: SqlDisclosureProps) {
  return (
    <details className="mt-2 text-sm">
      <summary className="cursor-pointer text-gray-500 hover:text-gray-700">Show SQL</summary>
      <pre className="mt-1 p-2 bg-gray-100 rounded text-xs font-mono overflow-x-auto">
        <code>{sql}</code>
      </pre>
    </details>
  );
}
```

### `ChartRenderer.tsx` Props Reminder

Already implemented. Call it as:
```typescript
<ChartRenderer
  chartConfig={response.chart_config}   // ChartConfig (not null — guard before rendering)
  columns={response.columns}
  rows={response.rows}
/>
```

### Message Thread Structure

```typescript
// Local type in useAnalytics.ts or ChatPanel.tsx
interface Message {
  id: string;               // crypto.randomUUID() or Date.now().toString()
  role: "user" | "assistant";
  text: string;             // user: question text; assistant: response.answer
  response?: AnalyticsQueryResponse;  // only on assistant messages
}
```

### Known Review Findings from Story 1.7 (Pre-Existing)

These are already flagged as deferred — do NOT fix them in this story:
- Stub components returning `<div>` placeholder (this story replaces them)
- Badge CSS vars have no dark-mode override (Story 3.7 scope)

### Out-of-Scope for This Story

| Concern | Belongs To |
|---------|-----------|
| Error toast with countdown timer | Story 5.6 |
| Upload panel UI | Story 3.7 |
| Confidence badge rendering | Story 3.7 |
| Vercel deployment | Story 6.3 |
| Any backend changes | Story 2.4 (planner fix), Story 2.5 (schema endpoint) |
| E2E / automated tests | Story QA (if installed) |

Story 2.5 (schema endpoint — `backlog`) provides `GET /api/schema`. DatasetStatus should handle the case where the endpoint returns 404 or fails gracefully (show "Schema unavailable").

### Files to Create / Modify

**Modify:**
- `frontend/src/types/api.ts` — add `SchemaInfoResponse` types + fix `AnalyticsQueryRequest`
- `frontend/src/hooks/useAnalytics.ts` — replace stub with implementation (or extend if 2.4 done first)
- `frontend/src/components/ChatPanel.tsx` — replace stub with full implementation
- `frontend/src/components/DatasetStatus.tsx` — replace stub with schema-fetching card
- `frontend/src/components/SqlDisclosure.tsx` — replace stub with collapsible SQL block
- `frontend/src/components/ResultTable.tsx` — replace stub with data table

**Do NOT modify:**
- `frontend/src/components/ChartRenderer.tsx` — already fully implemented
- `frontend/src/app/page.tsx` — tab switcher already correct
- `frontend/src/lib/api.ts` — axios instance already correct
- `frontend/src/app/globals.css` — Tailwind + CSS vars already set

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- **Story 2.4 already implemented `useAnalytics.ts`** — hook existed with `isQuerying`, `result`, `error`, `previousSql`, `query()`, `reset()` state. Extended (not replaced) to add `messages: Message[]` for the chat thread. Existing `previousSql` tracking retained.
- **`AnalyticsQueryRequest` type mismatch fixed** — `previous_sql` was incorrectly nested under `context` in `types/api.ts`. Fixed to be a top-level field matching the actual backend Pydantic schema.
- **`pnpm build` passes cleanly** — TypeScript strict, zero errors, zero warnings. Routes: `/` (Static), `/_not-found`.

### Completion Notes List

- Fixed `AnalyticsQueryRequest` in `src/types/api.ts`: `previous_sql` is now a top-level field (was incorrectly nested under `context`).
- Added `ColumnInfo`, `TableInfo`, `SchemaInfoResponse` interfaces to `src/types/api.ts` for `GET /api/schema` response.
- `DatasetStatus.tsx`: fetches `GET /api/schema` on mount, shows table names + row counts; graceful "Schema unavailable" fallback on error; uses `isLoadingSchema` boolean.
- `SqlDisclosure.tsx`: native `<details>`/`<summary>` collapsible block — no useState needed; collapsed by default; monospace `<pre><code>` body.
- `ResultTable.tsx`: `<table>` with column headers from `columns[]`, rows from `rows[][]`; alternating row backgrounds; "Showing X of Y rows" footer; "No results." fallback when empty.
- `useAnalytics.ts` extended: added `messages: Message[]` state + exported `Message` interface. `query()` appends user message before API call, appends assistant message on success, sets `error` on failure. `reset()` clears `messages` + `previousSql` + `error`.
- `ChatPanel.tsx`: full chat panel implementation — `DatasetStatus` at top, message thread with user/assistant bubbles, answer + SQL disclosure + result table + chart + follow-up chips per assistant message, loading bounce animation, error banner, textarea input (Enter to submit, Shift+Enter for newline), Clear button.
- `pnpm build` passes TypeScript-clean with `output: 'standalone'`.

### File List

Modified:
- `frontend/src/types/api.ts`
- `frontend/src/hooks/useAnalytics.ts`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/DatasetStatus.tsx`
- `frontend/src/components/SqlDisclosure.tsx`
- `frontend/src/components/ResultTable.tsx`

Not modified (already implemented or out of scope):
- `frontend/src/components/ChartRenderer.tsx` — already fully implemented
- `frontend/src/app/page.tsx` — tab switcher already correct
- `frontend/src/lib/api.ts` — axios instance already correct

### Senior Developer Review (AI)

**Outcome:** Changes Requested
**Date:** 2026-03-30
**Layers run:** Blind Hunter ✓ · Edge Case Hunter ✓ · Acceptance Auditor ✓
**Dismissed:** 6 · **Deferred:** 7 · **Action items:** 5

#### Action Items

- [x] [Review][Patch] Message IDs use `Date.now()` — collision possible on same-tick calls [frontend/src/hooks/useAnalytics.ts:21,42]
- [x] [Review][Patch] Response array fields not defensively guarded — `columns`/`rows`/`suggested_questions` null/undefined crashes render [frontend/src/hooks/useAnalytics.ts:37-45]
- [x] [Review][Patch] `schema.tables` not guarded — null/undefined response crashes DatasetStatus [frontend/src/components/DatasetStatus.tsx:18]
- [x] [Review][Patch] Missing `aria-label` on "Ask" button (announces "…") and no `role="status"` on loading dots [frontend/src/components/ChatPanel.tsx:~145,~108]
- [x] [Review][Patch] API-level `response.error` shown as tiny inline text, not a banner — violates AC2 / error banner constraint [frontend/src/components/ChatPanel.tsx:~65]
- [x] [Review][Defer] No AbortController cleanup on unmount in DatasetStatus/useAnalytics — pre-existing React pattern, out of scope
- [x] [Review][Defer] Axios structured error (`retry_after`, backend message) not surfaced — Story 5.6 scope
- [x] [Review][Defer] ChartRenderer silent empty chart on x_key/y_key mismatch — pre-existing, not this story
- [x] [Review][Defer] ChartRenderer no row cap before Recharts render — pre-existing, not this story
- [x] [Review][Defer] ResultTable zero-row result hides column headers — acceptable POC UX
- [x] [Review][Defer] `rowCount` label can show "Showing N of 0 rows" on backend count mismatch — backend data integrity issue
- [x] [Review][Defer] `t.row_count.toLocaleString()` throws if backend sends null — Pydantic guarantees non-null int

### Review Follow-ups (AI)

- [x] [Review][Patch] Replace `Date.now()` IDs with `crypto.randomUUID()` [frontend/src/hooks/useAnalytics.ts]
- [x] [Review][Patch] Add defensive array defaults: `data.columns ?? []`, `data.rows ?? []`, `data.suggested_questions ?? []` [frontend/src/hooks/useAnalytics.ts]
- [x] [Review][Patch] Guard `schema?.tables ?? []` in DatasetStatus render [frontend/src/components/DatasetStatus.tsx]
- [x] [Review][Patch] Add `aria-label="Send question"` to Ask button, `role="status"` + `aria-label="Loading"` to loading indicator [frontend/src/components/ChatPanel.tsx]
- [x] [Review][Patch] Promote API-level `response.error` to use the same red banner style as network errors [frontend/src/components/ChatPanel.tsx]

## Change Log

- 2026-03-30: Story 2.6 created by create-story workflow
- 2026-03-30: Story 2.6 implemented — Chat Panel UI with full analytics interaction. `pnpm build` passes TypeScript-clean.
- 2026-03-30: Code review complete — 5 patch findings, 7 deferred, 6 dismissed.
- 2026-03-30: All 5 review patches applied. `pnpm build` passes TypeScript-clean.
