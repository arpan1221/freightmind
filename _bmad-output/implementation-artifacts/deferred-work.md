# Deferred Work

## Addressed in code (2026-03-30)

The following backlog items from this file were implemented or superseded:

- **6.2 / 1.1 — Non-root backend image:** `backend/Dockerfile` runs as `appuser` (uid 1000). Compose note added for `./backend/cache` writability when mounting the volume.
- **5.6 — Schema load error toast:** `frontend/src/app/page.tsx` refetches `/api/schema` when `retry_after` countdown completes (`onCountdownComplete` → `loadSchema()`).
- **5.5 — Duplicate primary/fallback models:** `Settings` logs a warning at load when `analytics_model == analytics_model_fallback` or vision pair matches (`app/core/config.py`).
- **5.4 — DB vs invalid SQL:** `OperationalError` after verification returns **503** with `error_type: database_unavailable` only when the message suggests lock/contention (`"locked"`); other operational errors (e.g. bad column) stay **422** `sql_execution_error`.
- **3.1 / 3.4 — POST /extract semantics:** Unsupported media type → **415**; oversize upload → **413**; extraction failure → **500** with rollback; `max_upload_bytes` in settings (default 10 MiB).
- **1.3 — CORS:** `CORS_ORIGINS` env (`*` or comma-separated list) via `cors_allow_origins_list()` in `app/main.py`.
- **1.1 — pydantic-settings:** Explicit dependency in `backend/pyproject.toml`; `Settings` uses `SettingsConfigDict`.
- **3.6 — Pagination:** `GET /api/documents/extractions` supports `limit` (1–500, default 100) and `offset` (default 0).
- **4.1 — Intent vs empty-state:** `_should_answer_without_confirmed_extractions` runs **before** `classify_intent`; precheck failures are logged and the pipeline continues (preserves `query_failed` behavior when the DB is broken). Document-themed + zero confirmed now uses **zero** LLM calls for the empty-state path.
- **6.4 — Demo generator:** `generate_demo_invoices.py` wraps `main()` with `OSError` → `SystemExit` and message.
- **1.7 / .gitignore:** `*.db` at repo root already covers `freightmind.db` (no change required).

Remaining items below are still **manual**, **optional**, **out of scope** for this PoC, or **future security/scale** work unless explicitly picked up later.

---

## Deferred from: code review of 6-2-backend-deployment-to-render.md (2026-03-30)

- NFR12 (60s cold) and production HTTPS checks on `*.onrender.com` are operator-validated after Blueprint deploy; not stored in-repo.
- Optional: `uv run` cold path on first start — watch Render logs if deploy health exceeds expectations.

## Deferred from: code review of 6-4-synthetic-freight-invoice-demo-files.md (2026-03-30)

- AC1–AC2: Live vision validation (plausible fields, **LOW**/**NOT_FOUND**) remains manual; README documents steps — confirm before graded demo.
- Optional: CI smoke test that runs the generator in a tmpdir.

## Deferred from: code review of 6-3-frontend-deployment-to-vercel.md (2026-03-30)

- NFR6 (~5s cold start) and production CORS/chat smoke tests are documented in `frontend/VERCEL.md` but not evidenced by automated tests or deployment logs in-repo; confirm after Vercel + Render are wired.

## Deferred from: code review of 5-6-error-toast-ui-with-countdown-timer (2026-03-31)

_(Schema refetch on countdown: implemented — see “Addressed in code” above.)_

## Deferred from: code review of 5-5-automatic-fallback-model-on-primary-model-failure (2026-03-31)

- Optional integration test: `POST /api/query` (or extraction) with double-failure mock → assert 503 JSON `error_type: model_unavailable` (unit tests already cover `ModelUnavailableError`).

## Deferred from: code review of 5-4-invalid-or-unsafe-sql-structured-error-with-failed-query (2026-03-31)

- Further refinement: distinguish transient DB issues from bad SQL using richer heuristics than `"locked"` alone if needed in production.

## Deferred from: code review of 1-1-scaffold-backend-project-with-uv-fastapi-and-docker (2026-03-30)

- `depends_on` without `condition: service_healthy` — needs healthcheck stanza introduced in Story 1.4 before actionable.
- `settings = Settings()` at module level crashes at import if `OPENROUTER_API_KEY` missing — mitigated once lifespan has startup validation (Stories 1.2/1.3).
- `docker-compose env_file: ./backend/.env` fails on missing file at fresh clone — mitigated once `backend/.env.example` is present and setup docs reference it.
- No lifespan error handling — relevant when DB init and CSV load are added in Stories 1.2/1.3.
- `os.environ.setdefault` at module level in tests mutates process env — only a concern if missing-key tests are added; current suite unaffected.

## Deferred from: code review of 1-4-health-check-endpoint (2026-03-30)

- NFR14 500ms vs 3s model timeout — AC3 says "within 500ms" but the httpx timeout is 3s; spec is internally inconsistent. Deferred: address in a future performance/hardening story with asyncio.wait_for outer deadline if needed.
- No backoff/caching on model check calls — every health probe makes a live HTTP request to OpenRouter; thundering-herd risk if service is down. Deferred to Epic 5 (resilience stories).
- DB connection has no timeout — SQLite SELECT 1 via connection pool has no pool-exhaustion timeout; low risk for local SQLite but worth addressing in production hardening (Epic 6 deployment story).

## Deferred from: code review of 1-3-auto-load-scms-csv-into-shipments-table-on-cold-start (2026-03-30)

- CORS `allow_origins=["*"]` (or broad lists) with no credential restriction — tighten origins in production deployments.
- Multi-worker startup race: idempotency count check is TOCTOU; concurrent workers both see count=0 and attempt full insert, causing duplicate-PK errors — current deploy is single-worker uvicorn; address if scaling to multiple workers.
- `CSV_PATH` resolved at module import time with no env-var override — safe in Docker; address if non-standard deploy layout is needed.
- `TestClient(app)` in test_story_1_1.py writes to live `freightmind.db` — test isolation concern; pre-existing from Story 1.1.
- `autoincrement=False` not set on `Shipment.id` primary key — safe in SQLite; would conflict with Postgres SERIAL on future migration.

## Deferred from: code review of 1-5-prompt-registry-all-prompt-templates-as-txt-files (2026-03-30)

- No `PROMPTS_DIR` existence check at import time — unusual deployment layout (e.g., missing prompts dir in an installed package) gives a misleading `FileNotFoundError` pointing at the file, not the directory. Acceptable for current uv-run deploy model.
- `PermissionError` from `path.read_text()` propagates unhandled with no additional context — worth wrapping with context in a production-hardening pass.

## Deferred from: code review of 1-2-auto-create-database-schema-and-indexes-on-startup (2026-03-30)

- Side-effect model imports in `main.py` are fragile — new models must be manually added or tables won't be created; consider a model registry pattern.
- `engine` module-level instantiation with relative SQLite path `./freightmind.db` — CWD-relative; correct in Docker, may misbehave in local dev outside Docker.
- `test_foreign_key_constraint_enforced` FK PRAGMA scope — may be fragile with SQLAlchemy 2.x connection pooling resetting PRAGMA state per-connection.

## Deferred from: code review of 1-7-scaffold-frontend-project-with-nextjs-typescript-tailwind-and-docker (2026-03-30)

- Stub components return `<div>` placeholder not `null` — by design for this story; real implementations added in Stories 2.6 (ChatPanel) and 3.7 (UploadPanel).
- Badge CSS vars (`--badge-high`, `--badge-medium`, etc.) have no dark-mode override in `globals.css` — purely presentational; ConfidenceBadge rendering is Story 3.7 scope.
- `freightmind.db` not included in root `.gitignore` — pre-existing from Story 1.2; not introduced by this story.

## Deferred from: code review of 1-6-modelclient-with-file-based-sha-256-response-cache (2026-03-30)

- Non-JSON-serialisable values in `messages` raise `TypeError` — caller responsibility; `messages: list[dict]` contract requires JSON-serialisable dicts.
- Concurrent writes to same cache key share a single `.tmp` filename — `asyncio` is single-threaded; multi-process cache safety out of scope for this dev tool.
- `httpx.AsyncClient` is never closed — graceful shutdown / lifecycle management is Epic 6 scope.
- `settings.cache_dir = "./cache"` is CWD-relative — pre-existing design in `config.py`; absolute path resolution can be added in deployment hardening (Epic 6).
- Sensitive prompt/response data stored in plaintext cache files — by design for development quota management; encryption/ACL hardening out of scope.
- API errors (`openai.APIError`, `httpx.TimeoutException`) propagate raw — explicitly deferred to Epic 5 (stories 5.2 retry, 5.3 rate-limit, 5.5 fallback).

## Deferred from: code review of 2-1-analytics-pipeline-post-api-query-planner-executor-verifier (2026-03-30)

- No authentication on POST /api/query — POC scope; auth is an Epic-level architectural concern.
- Internal DB/LLM error details exposed via `message=str(e)` in error responses — pre-existing pattern; harden before production (Epic 6).
- `ModelClient` instantiated per-request, no HTTP connection pooling — performance optimization; refactor to app-scoped singleton (Epic 6).
- `previous_sql` client-controlled, passed verbatim to LLM prompt — by design for Story 2.4 follow-up queries; prompt-injection defense is out of scope here.
- Prompt injection via raw DB row values included in answer-generation LLM context — architectural LLM security concern; harden before production.
- No aggregate request timeout; 5 sequential LLM calls can exceed NFR1 15s budget — Epic 5 resilience scope (story 5.2 retry handles partial overlap).

## Deferred from: code review of 2-2-out-of-scope-detection-null-surfacing-and-follow-up-suggestions (2026-03-30)

- `_count_null_exclusions` hardcodes `shipments` table — by design for single-table system; if LLM generates queries over joins or other tables, null counts are computed against `shipments` regardless. Address when multi-table queries are introduced (Epic 4).
- Prompt injection via raw `body.question` in LLM messages — user-controlled string inserted verbatim into every LLM call; pre-existing from Story 2.1, not introduced here. Harden before production (Epic 6).
- `ModelClient` instantiated per-request — potential connection pool exhaustion under load; pre-existing from Story 2.1. Refactor to application-scoped singleton via FastAPI dependency injection (Epic 6).
- `previous_sql` accepted without validation from client and forwarded to LLM — pre-existing from Story 2.1.
- `rows: list[list]` untyped inner list — non-serializable DB types (Decimal, datetime) silently coerce or cause 500; pre-existing schema design from Story 2.1.
- DB cursor returned by `db.execute()` not explicitly closed — pre-existing from Story 2.1.
- Dirty session state possible if `result.fetchall()` raises after `db.execute()` — `_count_null_exclusions` could run on a dirty session; SQLAlchemy session lifecycle hardening is Epic 5/6 scope.

## Deferred from: code review of 2-3-chart-configuration-generation (2026-03-30)

- Log truncation at 100 chars in `_generate_chart_config` warning — minor debug ergonomics, pre-existing pattern (`_generate_follow_ups` uses same truncation). No functional impact.
- No test for LLM-hallucinated column names in `x_key`/`y_key` — contract/integration test concern requiring live LLM or sophisticated mock; not actionable as a unit test.

## Deferred from: code review of 2-4-stateless-follow-up-query-with-previous-sql-context (2026-03-30)

- No guard against concurrent `query()` calls while `isQuerying === true` — UI responsibility to disable submit button while loading; hook itself need not enforce this.
- `reset()` does not cancel in-flight requests — pending API calls will still resolve and append to `messages` after reset; requires `AbortController` pattern; pre-existing UX design gap.
- `previousSql` exposed in hook return (internal implementation detail) — spec explicitly requires it; revisit whether to hide it at Epic 2 completion when UI is fully integrated.
- `classify_intent` exception handling uses broad `ValueError` catch and returns soft-failure dict — pre-existing Story 2.2 behavior, not introduced by this story.
- Test message extraction pattern `call_kwargs.kwargs.get("messages") or call_kwargs.args[1]` is fragile — pre-existing project testing convention, consistent across all story tests.

## Deferred from: code review of 2-5-schema-endpoint-get-api-schema (2026-03-30)

## Deferred from: code review of 2-7-analytics-agent-standalone-invocability (2026-03-30)

- `_make_mock_client` side_effect list has no guard against pipeline call-count changes — if a 7th LLM call is added the mock raises `StopAsyncIteration` instead of a clear assertion error; pre-existing pattern across all story tests.
- AST scan misses `importlib.import_module()` dynamic imports — speculative; no dynamic imports in codebase.
- Incomplete in-memory schema (5 cols vs full shipments model) — intentional; mock SQL is `COUNT(*)` only and does not reference missing columns.
- `os.environ.setdefault` does not affect already-instantiated `settings` singleton — pre-existing pattern used in every test file.

## Deferred from: code review of 2-5-schema-endpoint-get-api-schema (2026-03-30)

- SQL f-string interpolation for table/column identifiers in `get_schema` — ORM-controlled constants, double-quote mitigation in place; project-wide pattern; not exploitable via user input.
- No authentication on `/schema` endpoint — information disclosure concern; auth is not implemented anywhere in the project and is out of story scope.
- `_check_model` swallows exceptions without logging root cause — pre-existing health check code, not changed by this story.
- `SessionLocal()` UnboundLocalError risk if constructor raises in health check — pre-existing health check behavior.
- `sample_values: list` bare typing (no `list[Any]`) — intentionally specified in dev notes for mixed-type columns (int, float, str); Pydantic serializes all primitives correctly.
- `Base.metadata.tables` can enumerate unmigrated tables during rolling deploys — inherent to spec-prescribed approach; address in deployment hardening (Epic 6).
- API key sent in `Authorization` header on every health probe — pre-existing health check behavior, not changed by this story.
- `setup_method` teardown pattern (overrides cleared before test, not after) — established project convention used across all story tests.

## Deferred from: code review of 2-6-chat-panel-ui-full-analytics-interaction (2026-03-30)

- No AbortController cleanup on component unmount in DatasetStatus/useAnalytics — pre-existing React pattern, applies to entire codebase; address in a dedicated cleanup pass.
- Axios structured error payload (`retry_after`, backend `message`) not surfaced to user — Story 5.6 owns rate-limit error UX with countdown timer.
- ChartRenderer renders silent empty chart when `x_key`/`y_key` don't match column names — pre-existing ChartRenderer; address when ChartRenderer is hardened.
- ChartRenderer passes all rows to Recharts with no row cap — pre-existing; Recharts handles moderate datasets fine for POC; address in performance hardening.
- ResultTable zero-row result shows "No results." instead of column headers — acceptable POC UX; can be improved for production.
- `rowCount` footer can show "Showing N of 0 rows" if backend sends mismatched count — backend Pydantic model guarantees correct count; address if backend sends wrong data.
- `t.row_count.toLocaleString()` would throw if backend sends null for row_count — Pydantic guarantees non-null `int`; no action needed unless backend schema changes.

## Deferred from: code review of 3-4-confirm-endpoint-post-confirm-extraction-id (2026-03-30)

- `_parse_line_items` `int()` cast raises `ValueError` on float strings (e.g., "2.5") — no try/except around conversion; Story 3.1 scope.
- No tests for `post_extract` endpoint — Story 3.1 scope; address when Story 3.1 is reviewed.
- `confirmed_by_user` uses magic integers 0/1 with no type safety — pre-existing model from Story 1.2; address in production hardening if boolean type is needed.
- `ExtractionResponse.extraction_id=0` used as invalid sentinel on failure — not a valid PK value but could confuse clients; Story 3.1 scope.
- Numeric correction values not type-coerced before `setattr` (e.g. string `"not_a_number"` for a Float column) — POC-acceptable per spec dev notes; SQLite coerces silently; address in production hardening.
- `_HEADER_FIELDS` and `_ALLOWED_CORRECTION_FIELDS` are separately maintained duplicates — currently identical but will diverge intentionally in Story 3.2 (normalisation adds verify-time logic not needed for correction validation).
- Frontend `ConfirmRequest.extraction_id: string` vs backend `int` type mismatch — pre-existing in `frontend/src/types/api.ts`; Pydantic coerces JSON numbers correctly; align TypeScript type to `number` when Story 3.7 is implemented.
- `engine` return value unused and unclosed in test methods — cosmetic; in-memory SQLite has no real resource leak; low priority.

## Deferred from: code review of 3-2-normalisation-layer-mode-country-date-and-weight (2026-03-30)

- Two-letter ISO code matches (e.g., `"ng"`, `"tz"`) return HIGH confidence same as full-name matches — story 3.3 confidence scoring should differentiate alias vs. exact match.
- No MEDIUM/LOW confidence levels in normaliser — binary HIGH/NOT_FOUND is intentional for this story; story 3.3 scope to introduce graduated confidence.
- Two-digit year century ambiguity: Python's 68/69 pivot rule applies to `%y` formats — low probability for freight docs in current decade; address if historical date handling needed.
- Internal double-whitespace in date strings (e.g., `"March  5, 2024"`) fails all `strptime` formats — OCR normalisation pre-processing out of scope for this story.
- ISO datetime with time component (e.g., `"2024-01-15T10:30:00"`) returns NOT_FOUND — time stripping out of scope; upstream extraction should output date-only.
- European decimal comma (`"1,5 kg"`) silently misparsed as `"15 kg"` after comma removal — LLM extractions expected in English locale; address if multi-locale extraction is required.
- Zero weight `"0 kg"` accepted with HIGH confidence — semantically suspicious for freight; story 3.3 confidence scoring context should handle this.

## Deferred from: code review of 3-5-cancel-endpoint-delete-extract-extraction-id (2026-03-30)

- SQLite FK enforcement not enabled in tests — pre-existing pattern across all test files; ORM-level cascade covers the tested scenario.
- No auth/IDOR guard on DELETE endpoint — no auth anywhere in the project; Epic 6/production hardening scope.
- JSONResponse bypasses response_model for 404 error path — pre-existing design pattern; spec explicitly specifies this approach.
- `test_endpoint_in_openapi_spec` uses real TestClient without DB override — pre-existing convention from test_story_3_4.py; only hits OpenAPI schema, no DB.
- `dependency_overrides` not cleared in teardown_method — pre-existing project convention; cleanup in setup_method is established pattern.
- No guard for deleting confirmed extraction (`confirmed_by_user=1`) — spec-intentional: "leave deletion unrestricted for now — Story 3.4 is the business guard".
- Route at `/api/extract/{id}` outside `/documents` namespace — spec-mandated path; intentional API design choice.

## Deferred from: code review of 3-3-confidence-scoring-per-field (2026-03-30)

- `validate_corrections()` numeric type gap — string values written to Float DB columns; Story 3.4 scope.
- `low_confidence_fields` covers header fields only (not line items) — intentional design choice, consistent with ExtractionResponse schema and tests.
- `_HEADER_FIELDS` and `_ALLOWED_CORRECTION_FIELDS` duplicated — drift risk; single source of truth would reduce maintenance burden.
- `_VALID_SHIPMENT_MODES` case-sensitive with no input normalisation in `validate_corrections()` — Story 3.4 scope.
- `_parse_line_items()` silently drops non-dict items with no debug log — minor observability gap.
- `validate_corrections()` `document` parameter accepted but unused — placeholder for future field-level cross-validation.
- `int(qty)` silently truncates float quantities (`1.9 → 1`) — consistent with existing `_parse_line_items()` behavior; address if invoice line-item precision matters.
- `validate_corrections()` accepts empty string as correction value — Story 3.4 scope.
- `score_confidence()` processes open field set (accepts any LLM-returned key) — intentional per spec Dev Notes; may propagate hallucinated fields downstream.

## Deferred from: code review of 3-8-vision-extraction-standalone-invocability (2026-03-30)

- Raw SQL schema drift from SQLAlchemy models not detected — test DDL is hand-written; new ORM migrations won't auto-update test schema; accepted tradeoff consistent with story 2.7.
- `os.environ.setdefault` at module level mutates process env for lifetime of test process — only a concern if missing-key tests are added; pre-existing project-wide pattern.
- Router prefix asymmetry: `documents.router` has `/documents` prefix, `extraction.router` has none — fragile if someone adds a prefix to `extraction.router` without updating include calls; pre-existing design, not introduced here.
- `ModelClient` patched with bare MagicMock (no spec) — could silently satisfy wrong signatures; acceptable for isolation tests where the client is never reached; pre-existing pattern.

## Deferred from: code review of 3-1-file-upload-endpoint-post-extract (2026-03-30)

- Fence-stripping regex in `executor.py` doesn't handle preamble prose before code fences — LLM response like "Here is the JSON:\n```json\n{...}\n```" leaves preamble after substitution; pre-existing Epic 2 pattern; address in LLM response hardening pass.
- Multi-page PDF silently converts only page 0 — `planner.py:27` documented as Story 3.1 single-page limitation; address in Story 3.8 or a dedicated multi-page enhancement.
- `/confirm` endpoint included in `documents.py` ahead of Story 3.4 scope — pre-existing Story 3.4 pre-work; tests pass and behavior is correct; no action needed before Story 3.4 review.
- `validate_corrections()` in `verifier.py` ahead of Story 3.4 scope — same as above.
- TOCTOU race on `confirmed_by_user` in `post_confirm` — two concurrent confirm requests can both pass the 409 guard; address with SELECT FOR UPDATE or DB uniqueness constraint in Story 3.4 review.
- Hard-coded `confidence=0.9` for line items in `documents.py:83` — `ExtractedLineItemOut.confidence` is ignored when building ORM `ExtractedLineItem`; Story 3.3 will add real per-line-item confidence.
- `ModelClient` instantiated per-request in `post_extract` — no HTTP connection pool reuse; pre-existing pattern from Epic 2; refactor to app-scoped singleton in Epic 6.

## Deferred from: code review of 3-6-extracted-documents-list-get-extractions (2026-03-30)

- `except Exception` breadth in `get_extractions` swallows all failures into `500 internal_error` — spec-mandated; revisit in Epic 5 global error handler story (5-1).
- `total_freight_cost_usd` IEEE 754 specials (NaN/Inf) pass Pydantic `float | None` but break JSON serialisation — applies to all float extraction fields; address in Epic 5 or with a custom Pydantic validator.
- No auth/authentication on `GET /extractions` — all routes in this project are currently unauthenticated; auth belongs to a future security story.
- `confirmed_by_user IS NULL` rows silently excluded from list — raw SQL inserts bypassing ORM defaults could leave NULLs; constrain at DB level in a future migration.
- `invoice_date` (and similar string date fields) have no format validation — free-form strings from LLM extraction; add normalization/validation in Epic 5 or a dedicated data quality story.
- `source_filename` `nullable=False` not enforced at SQLite engine level — a NULL value from a raw insert would cause a Pydantic `ValidationError` caught silently by `except Exception`; enforce at DB level in a future migration.

## Deferred from: code review of 3-7-upload-panel-ui-drag-and-drop-review-table-confidence-badges-edit-confirm-cancel (2026-03-30)

- Stale closure in `confirm()` reads `state` directly — in practice React re-renders on every `setState` so `confirm` always sees latest state; low practical risk; revisit if hook is refactored to use `useCallback` with deps.
- File MIME type spoofing — `file.type` is browser-controlled and spoofable; no server-side magic-byte validation visible; backend should validate on its side.
- `key={i}` on line items uses array index — line items list never reorders client-side so no reconciliation bugs in practice; fix if list becomes dynamic.
- SVG icons missing `aria-hidden="true"` — decorative icons announced by screen readers; address in a dedicated accessibility pass.
- No `onDragLeave` handler — no visual drag-enter/leave state toggle; UX polish out of scope for this story.
- Error state hides placeholder — `!error && <placeholder>` removes bottom placeholder card when error shown, leaving empty space; minor layout polish.

## Deferred from: code review of 4-1-schema-aware-planner-both-tables-in-analytics-prompt-context (2026-03-30)

- Regex heuristics for document-themed questions may miss rare paraphrases — user may get an empty result set from generated SQL instead of the no-confirmed short-circuit; expand patterns if product/support feedback warrants it.
