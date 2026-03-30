# Deferred Work

## Deferred from: code review of 1-1-scaffold-backend-project-with-uv-fastapi-and-docker (2026-03-30)

- No non-root user in Dockerfile — security hardening; belongs to deployment story 6.2.
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

- CORS `allow_origins=["*"]` with no credential restriction — pre-existing from Story 1.1; harden before production.
- Multi-worker startup race: idempotency count check is TOCTOU; concurrent workers both see count=0 and attempt full insert, causing duplicate-PK errors — current deploy is single-worker uvicorn; address if scaling to multiple workers.
- `CSV_PATH` resolved at module import time with no env-var override — safe in Docker; address if non-standard deploy layout is needed.
- `pydantic-settings` not declared in `pyproject.toml` — pre-existing from Story 1.1; verify transitive dependency or add explicit declaration.
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
