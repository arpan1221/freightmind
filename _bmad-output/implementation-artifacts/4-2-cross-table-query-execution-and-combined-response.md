# Story 4.2: Cross-table query execution and combined response

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created. -->

## Story

As a logistics analyst,
I want to ask questions that combine my uploaded invoices with historical shipment data in a single answer,
so that I can compare my specific invoices against the broader dataset.

## Acceptance Criteria

1. **Cross-table SQL (FR27)**  
   **Given** at least one confirmed extraction (`confirmed_by_user=1`) and the SCMS dataset are present  
   **When** `POST /api/query` is called with a cross-table question (e.g., compare uploaded invoice freight costs to the dataset average for that shipment mode)  
   **Then** the Executor produces a SQL query using `JOIN` or `UNION` spanning `shipments` and `extracted_documents`  
   **And** the generated SQL is validated by `AnalyticsVerifier` and executed via `session.execute(text(sql))` unchanged.

2. **Combined narrative answer (FR26)**  
   **Given** the cross-table query executes successfully  
   **When** the response is returned  
   **Then** the `answer` field presents a combined interpretation that clearly draws on both sources (not only one table).

3. **Performance (NFR1)**  
   **Given** a cache miss  
   **When** the full pipeline runs for such a question  
   **Then** the HTTP response completes within 15 seconds under normal conditions.

4. **Execution path**  
   **Given** the generated SQL passes the Verifier  
   **When** it runs  
   **Then** no special-case branch is required for multi-table SELECTs — same execution path as single-table analytics.

## Tasks / Subtasks

- [x] **Dependency / ordering (AC 1–4)**  
  - [x] Complete or coordinate with **Story 4.1** (`_bmad-output/implementation-artifacts/4-1-schema-aware-planner-both-tables-in-analytics-prompt-context.md`): dual-table prompts (`analytics_planner.txt`, `analytics_system.txt`, `analytics_sql_gen.txt`) must already describe both tables. Story **4.2** adds **linkage** behaviour: `JOIN` / `UNION ALL` across `shipments` + `extracted_documents` when the question compares or combines sources [Source: `DATASET_SCHEMA.md` §Linkage Query Examples].  
  - [x] If 4.1 left `analytics_sql_gen.txt` with single-table bias, extend it here so the model is explicitly encouraged to emit **cross-table** `JOIN` / `UNION ALL` for comparison questions; keep **read-only** SQL only.

- [x] **Executor behaviour (AC 1)**  
  - [x] Ensure `AnalyticsExecutor.generate_sql` continues to return a single SELECT (or compound SELECT via `UNION`/`UNION ALL`); strip fences only — no string interpolation of user text into SQL.  
  - [x] Align prompt rules with verifier: no `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc. (matches existing `AnalyticsVerifier`).

- [x] **Verifier (AC 1, 4)**  
  - [x] Reconcile epic NFR8 (unsafe ops on `shipments`) with current global keyword check in `backend/app/agents/analytics/verifier.py`: today **any** `INSERT`/`UPDATE`/… in the statement fails. Document that cross-table analytics must remain **SELECT-only**; do not weaken write protection.

- [x] **Route / answer layer (AC 2)**  
  - [x] Confirm `backend/app/api/routes/analytics.py` `_generate_answer` receives `columns`/`rows` from multi-table results and that `load_prompt("analytics_answer")` instructions produce a **combined** narrative when multiple logical sources appear in `SQL` or column labels.  
  - [x] If needed, lightly adjust `analytics_answer.txt` to ask the model to name both datasets when the SQL references both tables.

- [x] **NULL / sentinel behaviour (FR7 continuity)**  
  - [x] Review `_count_null_exclusions` in `analytics.py`: it currently counts NULLs only on **`shipments`** via `SELECT COUNT(*) FROM shipments WHERE "col" IS NULL`. For cross-table SQL, either extend this safely for `extracted_documents` where relevant, or document a deliberate limitation for this story so the answer text does not claim exclusions that were not computed. Prefer minimal, correct behaviour over silent wrong counts.

- [x] **Tests**  
  - [x] Add `backend/tests/test_story_4_2.py` (or extend analytics tests): with **mocked** LLM returning a fixed `UNION ALL` or `JOIN` SQL spanning both tables, assert **200** response, non-empty `sql`, `rows`, and `answer`; assert **no** raw user text in executed SQL.  
  - [x] Use a test DB session / fixtures with at least one confirmed `extracted_documents` row and known `shipments` rows so execution is deterministic.

## Dev Notes

### Scope and prerequisites

- **Epic 4 goal:** UNION/JOIN across `shipments` + `extracted_documents` [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 4].  
- **Story 4.1** supplies schema-aware planner context; **this story** ensures the **Executor + SQL prompt + answer** path actually produces and runs linkage SQL and returns a **combined** answer. If `analytics_sql_gen.txt` still only names `shipments` (current state), cross-table SQL will not reliably satisfy AC 1 — fix that here or ensure 4.1 lands first without duplication.

### Canonical join / comparison patterns

Use [Source: `DATASET_SCHEMA.md` §Linkage Query Examples]: `UNION ALL` with a `source` column, `AVG` comparisons with `WHERE confirmed_by_user = 1` on `extracted_documents`, and consistent vocabulary for `country` / `shipment_mode` (see §Synthetic Invoice Field Mapping).

### Architecture compliance

- **Raw SQL execution:** `session.execute(text(generated_sql))` — same as architecture hybrid pattern [Source: `_bmad-output/planning-artifacts/architecture.md` — Data Architecture].  
- **No user text in SQL:** Question only in LLM messages; never f-string into SQL [Source: epics — NFR7].  
- **Model gateway:** All LLM calls via `ModelClient` [Source: epics — Additional Requirements].  
- **Prompts:** Prefer `.txt` in `backend/app/prompts/`; avoid new inline prompt strings in Python [Source: FR40].

### Project structure — files likely touched

| Area | Path |
|------|------|
| SQL generation prompt | `backend/app/prompts/analytics_sql_gen.txt` |
| Answer prompt (if needed) | `backend/app/prompts/analytics_answer.txt` |
| Executor | `backend/app/agents/analytics/executor.py` (only if API changes) |
| Verifier | `backend/app/agents/analytics/verifier.py` (confirm rules still match) |
| Route | `backend/app/api/routes/analytics.py` (`_generate_answer`, optionally `_count_null_exclusions`) |
| Tests | `backend/tests/test_story_4_2.py` |

### Testing standards

- **pytest** + **async** patterns consistent with `backend/tests/test_story_2_1.py` / `backend/tests/test_story_3_*.py`.  
- Mock `ModelClient` or patch `AnalyticsExecutor.generate_sql` / `Planner` to return deterministic SQL.  
- Assert response shape matches `AnalyticsQueryResponse` in `app/schemas/analytics.py`.

### Previous story intelligence

- **Story 4.1** (`4-1-schema-aware-planner-both-tables-in-analytics-prompt-context.md`): already specifies extending `analytics_planner.txt`, `analytics_system.txt`, and `analytics_sql_gen.txt` with `extracted_documents` and `confirmed_by_user` rules. **Story 4.2** builds on that by proving **linkage** SQL (JOIN/UNION) runs end-to-end and the **answer** text synthesises both sources. Do not revert 4.1’s empty-table handling; extend only where linkage-specific examples or NULL handling are missing.

### Git intelligence

- Recent history is sparse (`git log` shows foundational analytics commit). Rely on existing analytics tests and patterns in `backend/app/api/routes/analytics.py` rather than recent commits.

### Latest technical notes

- SQLite supports `UNION ALL`, `JOIN`, and subqueries; keep queries bounded (existing executor prompt uses `LIMIT` — preserve for large result sets).  
- **Chart:** `_generate_chart_config` requires `x_key`/`y_key` in `columns`; combined queries should expose column names compatible with charting when the result is quantitative.

### Project context reference

- No `project-context.md` in repo; use this file + `DATASET_SCHEMA.md` + `epics.md`.

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Verified implementation: `analytics_sql_gen.txt` includes FR27 cross-table rules and UNION ALL example; `analytics_answer.txt` requires dual-source interpretation when SQL references both tables.
- `analytics.py`: `_sql_crosses_shipments_and_extracted`, linkage note in `_generate_answer`, `_count_null_exclusions` documented as shipments-only for cross-table (docstring).
- `verifier.py` docstring documents SELECT-only multi-table policy.
- `backend/tests/test_story_4_2.py` covers UNION ALL execution, prompts, and helper. Full backend suite: **323 passed** (pytest with full permissions; sandbox run may segfault in unrelated numpy path in some environments).

### File List

- `backend/app/prompts/analytics_sql_gen.txt`
- `backend/app/prompts/analytics_answer.txt`
- `backend/app/api/routes/analytics.py`
- `backend/app/agents/analytics/verifier.py`
- `backend/tests/test_story_4_2.py`

### Change Log

- **2026-03-30:** Story 4.2 verified complete — dev-story workflow; sprint status aligned **done**.
- **2026-03-30:** Code review — `_sql_crosses_shipments_and_extracted` now strips SQL comments before detecting table names (aligns with null-exclusion logic); regression assertion in `test_story_4_2.py`.

### Review Findings (code review)

- [x] [Review][Patch] Cross-table detection could treat `shipments` as present when it appeared only in `--` comments — fixed by stripping comments before substring check [`analytics.py`, `test_story_4_2.py`].
- [x] [Review][Defer] NFR1 (15s) — no automated timing test; acceptable for PoC per completion notes.

## Story completion status

- **Status:** done  
- **Note:** NFR1 (15s) is an operational/SLA target — not asserted in unit tests; ModelClient timeout and route caps align with bounded latency.
