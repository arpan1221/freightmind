# Story 4.1: schema-aware-planner-both-tables-in-analytics-prompt-context

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a logistics analyst,
I want to ask natural language questions that query my uploaded invoice data using the same chat interface I use for historical shipments,
so that I don't need a separate tool to query documents I've already confirmed.

## Acceptance Criteria

1. **Given** at least one extraction has been confirmed (`confirmed_by_user = 1`)  
   **When** `POST /api/query` is called with a question referencing extracted documents (e.g. "How many invoices have I uploaded?")  
   **Then** the Planner-related prompts include the schema for both `shipments` and `extracted_documents` tables  
   **And** the generated SQL targets the correct table(s) (FR25).

2. **Given** the `extracted_documents` table is empty  
   **When** `POST /api/query` is called with a question about uploaded documents  
   **Then** the response answers honestly (e.g. no confirmed extractions yet) rather than surfacing a SQL execution error.

## Tasks / Subtasks

- [x] **Task 1 — Prompts: dual-table schema context (AC: 1)**  
  - [x] Extend `backend/app/prompts/analytics_planner.txt` so intent classification knows the analyst can ask about **historical SCMS shipments** and **confirmed uploaded extractions** (`extracted_documents`, `confirmed_by_user`). Questions that only concern confirmed invoice/ upload counts must classify as `answerable`, not `out_of_scope`.  
  - [x] Extend `backend/app/prompts/analytics_system.txt` (used by `AnalyticsPlanner.plan`) to describe both data sources at a high level so follow-up refinement stays consistent.  
  - [x] Extend `backend/app/prompts/analytics_sql_gen.txt` with full **`extracted_documents`** column list aligned with [Source: `backend/app/models/extracted_document.py`] and [Source: `DATASET_SCHEMA.md` — SQLite Schema — `extracted_documents`]. Include rules: only query invoice-level fields from `extracted_documents` unless the question needs line items; then join `extracted_line_items` on `document_id`. Prefer `confirmed_by_user = 1` when the user means “my confirmed invoices / uploads.”  
  - [x] Keep single source of truth: column names must match ORM/SQLite exactly (snake_case).

- [x] **Task 2 — Empty / no-confirmed path (AC: 2)**  
  - [x] Before or instead of executing failing SQL, detect “uploaded / invoice / extraction” intent when there are **no rows** in `extracted_documents` **or** no rows with `confirmed_by_user = 1` (choose the behaviour that matches the epic’s product rule: confirmed-only for analyst-facing “my data”). Document the chosen rule in code comments.  
  - [x] Return a normal `AnalyticsQueryResponse` with a clear `answer`, empty or minimal `sql`/`rows` as appropriate — **no unhandled DB exceptions** and no raw SQLite error strings to the client.

- [x] **Task 3 — Tests**  
  - [x] Add `backend/tests/test_story_4_1.py` with mocked `ModelClient` **or** prompt-content assertions, following patterns in `backend/tests/test_story_2_*.py`.  
  - [x] Cover: (a) prompts loaded for planner/executor include both table descriptions; (b) empty `extracted_documents` + document-themed question yields honest answer path; (c) with confirmed row(s) seeded, SQL path can target `extracted_documents` (mocked LLM returning a fixed SELECT).  
  - [x] Use in-memory SQLite + `StaticPool` where needed; align with existing analytics tests.

## Dev Notes

### Scope clarification (Planner vs Executor)

Epic wording says “Planner prompt”; in code, **intent** uses `analytics_planner.txt`, **question refinement** uses `analytics_system.txt`, and **SQL generation** uses `analytics_sql_gen.txt` via `AnalyticsExecutor` [Source: `backend/app/agents/analytics/planner.py`, `executor.py`]. All three must be updated for FR25 in this story — otherwise the model can classify document questions as out-of-scope or generate SQL that only references `shipments`.

### Architecture compliance

- **Raw SQL execution** for analytics unchanged: `session.execute(text(sql))` [Source: `backend/app/api/routes/analytics.py`].  
- **Verifier** currently only blocks unsafe keywords; it does not restrict table names [Source: `backend/app/agents/analytics/verifier.py`]. No change required unless you add table allowlisting (out of scope unless PRD changes).  
- **Schema endpoint** `GET /api/schema` already reflects all `Base.metadata` tables including `extracted_documents` [Source: `backend/app/api/routes/system.py`]. Optional: add a test that schema lists both tables — low priority vs prompt work.  
- **Linkage vocabulary:** Architecture notes that `destination_country` and `shipment_mode` should align with dataset vocabulary for linkage [Source: `_bmad-output/planning-artifacts/architecture.md`]. Prompts should not invent column names.

### Technical requirements

| Area | Requirement |
|------|----------------|
| `confirmed_by_user` | SQLite integer `0`/`1`; filter `= 1` for confirmed extractions. |
| `extracted_documents` columns | Match `ExtractedDocument` model: `id`, `source_filename`, `invoice_number`, `invoice_date`, `shipper_name`, `consignee_name`, `origin_country`, `destination_country`, `shipment_mode`, `carrier_vendor`, `total_weight_kg`, `total_freight_cost_usd`, `total_insurance_usd`, `payment_terms`, `delivery_date`, `extraction_confidence`, `extracted_at`, `confirmed_by_user`. |
| `extracted_line_items` | Optional in this story if AC only requires `extracted_documents`; include in `analytics_sql_gen` if questions might need line-level detail. |
| Model / config | Reuse `settings.analytics_model`; no new env vars expected. |

### File structure (expected touches)

- `backend/app/prompts/analytics_planner.txt`  
- `backend/app/prompts/analytics_system.txt`  
- `backend/app/prompts/analytics_sql_gen.txt`  
- `backend/app/api/routes/analytics.py` (empty/no-confirmed handling if implemented here)  
- `backend/tests/test_story_4_1.py` (new)

### Testing requirements

- pytest async tests consistent with existing backend tests.  
- Mock LLM where integration cost is high; assert prompt text or behaviour contractually.  
- Do not import extraction-only minimal app from story 3.8 unless testing isolation — full `app.main` is fine for route tests if existing tests do so.

### Previous story intelligence (Epic 3)

[Source: `_bmad-output/implementation-artifacts/3-8-vision-extraction-standalone-invocability.md`]

- Extraction pipeline must remain import-isolated from analytics for **extraction routes**; analytics **may** import DB models for both tables — that does not violate FR42.  
- Story 3.8 established minimal-app test patterns; reuse DB setup patterns but do not duplicate AST isolation tests unless needed.

### Project context reference

- No `project-context.md` in repo; use `DATASET_SCHEMA.md` and `TECH_DECISIONS.md` for linkage examples and vocabulary.

### Git intelligence summary

Recent history is sparse in this workspace snapshot; follow file patterns from stories 2.x and 3.x tests for consistency.

### Latest tech information

- Stack: FastAPI, SQLAlchemy 2.x, SQLite, existing `ModelClient` — no version bump required for this story.

## Dev Agent Record

### Agent Model Used

Composer (dev-story workflow)

### Debug Log References

- Full backend `pytest`: 319 passed (`tests/`).

### Completion Notes List

- Verified dual-table prompts (`analytics_planner`, `analytics_system`, `analytics_sql_gen`) and route-level **confirmed-only** short-circuit for document-themed questions when `COUNT(*) WHERE confirmed_by_user = 1` is zero (`analytics.py` helpers + comments).
- `analytics.py` uses `sqlalchemy.exc.OperationalError` in `_count_confirmed_extractions` to treat missing `extracted_documents` (minimal test DB) as zero confirmed rows; other DB errors propagate.

### File List

- `backend/app/prompts/analytics_planner.txt`
- `backend/app/prompts/analytics_system.txt`
- `backend/app/prompts/analytics_sql_gen.txt`
- `backend/app/api/routes/analytics.py`
- `backend/tests/test_story_4_1.py`
- `_bmad-output/implementation-artifacts/4-1-schema-aware-planner-both-tables-in-analytics-prompt-context.md` (this file — status/tasks only)

## Change Log

- 2026-03-30: Story 4.1 implemented — dual-table analytics prompts, no-confirmed extractions response path, tests; story marked **review**.
- 2026-03-30: Code review — extended `extraction` phrase heuristics; `review` → `done`.
- 2026-03-30: Follow-up — `_DOC_QUESTION_PATTERNS` extended for “my uploads” / “what did I upload” (AC2 short-circuit coverage); tests updated.
- 2026-03-30: Applied copy patch — “Documents tab” in no-confirmed message (matches `page.tsx`).

### Review Findings

- [x] [Review][Patch] Broaden `_DOC_QUESTION_PATTERNS` for extraction-only phrasing (e.g. “list my extractions”) — `backend/app/api/routes/analytics.py` (patterns near `Story 4.1 AC2`). Applied in review; test added in `tests/test_story_4_1.py`.

- [x] [Review][Defer] Intent classification runs before the no-confirmed-extractions short-circuit. If `classify_intent` returns `out_of_scope` for a document question, the user never gets the empty-state message — mitigated by dual-table planner prompt; reordering would be a product decision. — deferred, pre-existing pipeline ordering.

- [x] [Review][Patch] Completion notes incorrectly stated `OperationalError` was removed; implementation still requires it for missing-table handling — fixed in Dev Agent Record (`4-1` story file).

- [x] [Review][Patch] Heuristics for upload-only phrasing (`my uploads`, `what did I upload`) — `backend/app/api/routes/analytics.py`, `backend/tests/test_story_4_1.py`.

- [x] [Review][Patch] No-confirmed response copy referred to “extraction panel”; aligned with UI tab label **Documents** (`frontend/src/app/page.tsx`) — `backend/app/api/routes/analytics.py` `_no_confirmed_extractions_response`.

## Story completion status

- **Status:** done  
- **Note:** Code review complete; patch applied; one item deferred to deferred-work.md.
