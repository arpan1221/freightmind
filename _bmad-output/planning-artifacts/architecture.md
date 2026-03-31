---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
status: 'complete'
completedAt: '2026-03-30'
inputDocuments: ['_bmad-output/planning-artifacts/prd.md', '_bmad-output/planning-artifacts/product-brief.md', 'TECH_DECISIONS.md', 'DATASET_SCHEMA.md']
workflowType: 'architecture'
project_name: 'freightmind'
user_name: 'Arpan'
date: '2026-03-30'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 44 FRs across 7 capability areas:
- Natural Language Analytics (FR1–FR8): NL → SQL → result table + chart + follow-up context
- Document Upload & Vision Extraction (FR9–FR18): PDF/image → 14-field extraction → confidence scoring → normalisation (mode, country, date, weight)
- Extraction Review & Confirmation (FR19–FR24): Human-in-loop edit → confirm → store
- End-to-End Data Linkage (FR25–FR28): UNION/JOIN queries spanning both tables
- Failure Handling & Recovery (FR29–FR33): Structured errors, retry, model fallback
- System Transparency (FR34–FR37): Schema endpoint, health check, auto-docs, call logging
- Data Initialisation & Configuration (FR38–FR44): Startup CSV load, prompt registry, cache

**Non-Functional Requirements:** 15 NFRs driving key architectural decisions:
- Performance: cached < 2s, live analytics < 15s, live extraction < 30s, DB < 100ms
- Security: Verifier validates all SQL; no raw user input in SQL strings; HTTPS enforced; no secrets in repo
- Integration: OpenRouter timeout < 5s; cold Render deploy < 60s; SHA-256 cache keying; PyMuPDF < 5s per 10-page PDF

**Scale & Complexity:**
- Primary domain: Full-stack web application + LLM pipeline
- Complexity level: Medium-high
- Architectural components: ~6 backend modules, ~4 frontend React components, 3 SQLite tables

### Technical Constraints & Dependencies

- **Rate limit:** 50 req/day (shared across analytics + extraction agents) — file-based cache is mandatory, not optional
- **Ephemeral storage:** Render free tier resets SQLite on redeploy — startup script must be idempotent
- **Two LLM modalities:** Text/SQL (Llama 3.3 70B) and vision (Qwen3 VL 235B) must share one OpenRouter client with unified retry/fallback logic
- **Pre-decided stack:** Next.js 14 + FastAPI + SQLite + OpenRouter + PyMuPDF + Recharts (see TECH_DECISIONS.md — not up for re-evaluation)
- **Linkage correctness dependency:** `extracted_documents.destination_country` and `shipment_mode` must match dataset vocabulary exactly before storage; silent mismatch breaks FR25–FR28

### Cross-Cutting Concerns Identified

1. **Model Abstraction Layer** — shared OpenRouter client, rate limit tracking, retry with exponential backoff, model fallback, cache read/write — used by both agents
2. **Verifier Layer** — SQL safety validation (no DROP/DELETE/UPDATE on shipments), extraction field normalisation (mode/country vocabulary check) — gates all side effects
3. **Structured Error Shape** — `{error, message, retry_after}` used consistently across all 6 API endpoints; defined once as a Pydantic model
4. **DB Initialisation** — idempotent startup sequence: create tables if not exist → load CSV if shipments empty → create indexes → return health status
5. **Prompt Registry** — all LLM prompt templates in `backend/prompts/`; both agents reference this directory; zero inline strings in business logic (FR40)

---

## Starter Template Evaluation

### Primary Technology Domain

Monorepo: Next.js SPA (frontend) + FastAPI Python API (backend), deployed independently to Vercel and Render. No single starter covers both — each is initialised separately.

### Starter Options Considered

| Option | Verdict |
|--------|---------|
| `create-next-app@latest` (frontend) | Selected — official, maintains all decided stack choices |
| `tiangolo/full-stack-fastapi-template` | Rejected — includes PostgreSQL, React, JWT auth, Playwright; far more than needed |
| `uv init` + manual FastAPI structure (backend) | Selected — lightweight, idiomatic for API-only Python projects in 2026 |

### Frontend Initialisation

**Command:**
```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --turbopack \
  --import-alias "@/*"
```

**Current version:** Next.js 16.2.1 LTS (note: PRD referenced 14 — version updated, architectural choices unchanged)

**What this scaffolds:**
```
frontend/
├── src/
│   └── app/
│       ├── layout.tsx
│       ├── page.tsx
│       └── globals.css
├── public/
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

**Architectural decisions made by starter:**
- Language: TypeScript (strict mode)
- Styling: Tailwind CSS with PostCSS
- Bundler: Turbopack (default in 16.x)
- Routing: App Router (file-system based)
- Linting: ESLint with Next.js config
- Import alias: `@/*` maps to `src/`
- Directory: `src/app/` for pages and layouts

**Additional dependencies to install after init:**
```bash
pnpm add recharts axios
pnpm add -D @types/node
```

---

### Backend Initialisation

**Commands:**
```bash
uv init backend --python 3.12
cd backend
uv add "fastapi[standard]" uvicorn pymupdf openai python-multipart
uv add --dev ruff mypy
```

**Note:** `openai` Python SDK is used to call OpenRouter (OpenAI-compatible API — just change `base_url` to `https://openrouter.ai/api/v1`).

**Target project structure:**
```
backend/
├── app/
│   ├── main.py              # FastAPI app, lifespan startup hook
│   ├── core/
│   │   ├── config.py        # Pydantic BaseSettings (env vars)
│   │   └── database.py      # SQLite connection + initialisation
│   ├── agents/
│   │   ├── analytics/       # Planner, Executor, Verifier for SQL
│   │   └── extraction/      # Planner, Executor, Verifier for vision
│   ├── services/
│   │   ├── model_client.py  # Model Abstraction Layer (OpenRouter)
│   │   └── cache.py         # SHA-256 file cache
│   ├── api/
│   │   └── routes/          # analytics.py, documents.py, schema.py
│   ├── prompts/             # All LLM prompt templates (FR40)
│   └── schemas/             # Pydantic request/response models
├── data/
│   └── scms_shipments.csv   # Pre-loaded dataset
├── cache/                   # File-based response cache (gitignored)
├── pyproject.toml
└── uv.lock
```

**Development server:**
```bash
uv run fastapi dev app/main.py
```

**Note:** Project initialisation (both frontend and backend) should be Epic 1, Story 1 of implementation.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (block implementation):**
- DB access pattern: SQLAlchemy ORM (hybrid with raw SQL for analytics)
- CORS: wildcard origin for POC simplicity
- Multi-turn context: stateless (client holds previous_sql)
- Deployment: Docker for both local and Render

**Deferred Decisions (post-assignment):**
- Auth/roles: Part 2 scope
- Postgres migration: Phase 3
- SSE streaming: Phase 3

---

### Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB engine | SQLite via SQLAlchemy 2.x | ORM handles table creation + CSV loading + document writes; raw SQL execution via `session.execute(text(sql))` for LLM-generated analytics queries |
| Analytics query execution | Raw SQL via `sqlalchemy.text()` | Ensures the SQL shown to the user is exactly what runs — no ORM translation layer between LLM output and DB |
| Schema management | Declarative ORM models + `Base.metadata.create_all()` | Idempotent on every startup; no migrations needed for a POC |
| CSV loading | Pandas `read_csv()` → SQLAlchemy bulk insert | Loads only when `shipments` table is empty; handles sentinel value cleaning (NULL coercion) |
| Startup sequence | `lifespan` async context manager in `app/main.py` | FastAPI 0.135+ standard; runs DB init before first request is accepted |

**SQLAlchemy hybrid pattern:**
```python
# ORM: document writes, schema introspection
session.add(ExtractedDocument(...))
session.commit()

# Raw SQL: LLM-generated analytics (transparency requirement)
result = session.execute(text(generated_sql))
```

---

### Authentication & Security

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Authentication | None (Part 1) | Explicitly out of scope; POC demo context |
| CORS | Wildcard (`*`) | POC simplicity; acceptable for public demo with no auth |
| SQL injection protection | Verifier layer (FR29, NFR7/8) | All LLM-generated SQL validated before execution; no raw user input interpolated into SQL |
| Blocked SQL operations | `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER` on `shipments` | Verifier regex check on every generated query |
| Secrets management | `.env` locally; Render env vars in production | Never committed to repo (NFR10) |

---

### API & Communication Patterns

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | REST | FastAPI natural fit; auto-generates OpenAPI docs (transparency requirement) |
| OpenAPI docs | `/docs` (Swagger UI) + `/redoc` | Serves as the backend transparency layer for evaluators |
| Error shape | `{ "error": "type", "message": "human-readable", "retry_after": null\|int }` | Defined once as Pydantic `ErrorResponse` model; used across all endpoints |
| Multi-turn context | Stateless — client sends `previous_sql` in request body | Context survives Render cold restarts; no server-side session state; aligns with REST principles |
| Response streaming | None — synchronous request/response | Out of scope (Part 3 Vision); loading indicators handle UX |
| File upload | `multipart/form-data` via FastAPI `UploadFile` | Standard pattern for PDF/image uploads |

---

### Frontend Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API client | axios | Cleaner error handling (non-2xx throws by default); simpler multipart upload; interceptors for error toast |
| Backend URL config | `NEXT_PUBLIC_BACKEND_URL` env var | Vercel-standard pattern; different values for local dev vs production |
| State management | React `useState` + `useContext` | No Redux needed; `extraction_id` held in local component state between extract and confirm calls |
| Loading states | Per-request boolean flags in component state | 300ms loading indicator requirement (NFR5) |
| Chart rendering | Recharts — driven by `chart_config` from backend | Backend returns `{ type, x_key, y_key }`; frontend maps to Recharts component |

---

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend hosting | Vercel | Zero-config Next.js deployment; automatic HTTPS; free tier |
| Backend hosting | Render (Docker) | Containerised for portability; same image runs locally and in production |
| Local development | Docker Compose — runs frontend + backend together | Single `docker-compose up` for cold-start evaluation (Journey 5) |
| CSV data | Committed to repo under `backend/data/` | Deterministic cold start; ~2MB public domain data; no network dependency at startup |
| Backend start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | Render injects `$PORT`; `0.0.0.0` required for container networking |
| Environment config | `.env.example` committed; `.env` gitignored | Evaluator copies example file, adds API key — one step setup |
| Cache persistence | `cache/` volume in Docker Compose | Cache survives container restarts locally; committed for demo reproducibility option |

**Docker Compose structure:**

Evaluator setup: copy **repo root** `.env.example` to `.env` and set `OPENROUTER_API_KEY` (same file is referenced by Compose as `env_file: .env`). The frontend image is built with `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` so **browser** requests hit the published backend port on the host (not the Docker service hostname).

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./backend/cache:/app/cache
  frontend:
    build:
      context: ./frontend
      args:
        - NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
    ports: ["3000:3000"]
    depends_on: [backend]
```

### Decision Impact Analysis

**Implementation sequence (dependency order):**
1. Backend foundation: SQLAlchemy models + DB init + CSV loader + health check
2. Model Abstraction Layer: OpenRouter client + cache + retry + fallback
3. Analytics agent: Planner → Executor → Verifier → route
4. Vision extraction agent: Planner → Executor → Verifier → routes (extract + confirm)
5. Frontend: chat panel → upload panel → review panel
6. Integration: cross-table linkage queries + end-to-end smoke test
7. Deployment: Docker images + Vercel + Render + env config

**Cross-component dependencies:**
- Both agents depend on Model Abstraction Layer being complete first
- Extraction confirm endpoint depends on analytics schema (linkage queries need extracted_documents populated)
- Frontend chart rendering depends on backend `chart_config` response shape being stable
- Docker Compose local setup depends on backend Dockerfile being correct before frontend can connect

---

## Implementation Patterns & Consistency Rules

### Critical Conflict Points (8 identified)

JSON field casing, ORM/schema naming collision, agent internal layout, API response envelope, LLM call bypass, error shape, loading state naming, startup idempotency.

---

### Naming Patterns

#### Database & ORM

| Convention | Rule | Example |
|------------|------|---------|
| Table names | `snake_case`, plural | `shipments`, `extracted_documents` |
| Column names | `snake_case` | `freight_cost_usd`, `shipment_mode` |
| SQLAlchemy ORM models | `PascalCase`, singular, no suffix | `Shipment`, `ExtractedDocument` |
| Pydantic request schemas | `PascalCase` + `Request` suffix | `AnalyticsQueryRequest` |
| Pydantic response schemas | `PascalCase` + `Response` suffix | `AnalyticsQueryResponse` |
| Pydantic error schema | `ErrorResponse` (single shared model) | `ErrorResponse` |

#### API Endpoints

| Convention | Rule | Example |
|------------|------|---------|
| Resource nouns | Plural | `/api/analytics`, `/api/documents` |
| Action verbs | Noun + verb path segment | `/api/documents/confirm`, `/api/documents/extract` |
| Path parameters | `snake_case` | `/api/documents/{document_id}` |
| Query parameters | `snake_case` | `?shipment_mode=Air` |

#### Python Code

| Convention | Rule | Example |
|------------|------|---------|
| Functions & variables | `snake_case` | `generate_sql`, `extracted_fields` |
| Classes | `PascalCase` | `ModelClient`, `AnalyticsPlanner` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `CACHE_DIR` |
| Modules/files | `snake_case` | `model_client.py`, `analytics_executor.py` |
| Agent submodules | `{agent}_{role}.py` | `analytics_planner.py`, `extraction_verifier.py` |
| Prompt files | `{agent}_{purpose}.txt` in `prompts/` | `analytics_system.txt`, `extraction_fields.txt` |

#### TypeScript / Frontend

| Convention | Rule | Example |
|------------|------|---------|
| Components | `PascalCase` file + export | `ChatPanel.tsx`, `UploadPanel.tsx` |
| Custom hooks | `use` + `PascalCase` | `useAnalytics.ts`, `useExtraction.ts` |
| Variables & functions | `camelCase` | `previousSql`, `handleConfirm` |
| API response field access | `snake_case` — **no camelCase conversion** | `response.data.chart_config.x_key` |
| Loading state booleans | `is` + `PascalCase` verb | `isQuerying`, `isExtracting`, `isConfirming` |
| Event handlers | `handle` + `PascalCase` noun | `handleSubmit`, `handleFileUpload` |

---

### Structure Patterns

#### Backend Agent Layout

Every agent follows the identical three-file structure — no exceptions:

```
backend/app/agents/
├── analytics/
│   ├── __init__.py
│   ├── planner.py      # Intent classification — returns structured intent object
│   ├── executor.py     # LLM call via ModelClient — returns raw LLM output
│   └── verifier.py     # Validates output before any side effect
└── extraction/
    ├── __init__.py
    ├── planner.py      # Determines extraction strategy (single-page vs multi-page)
    ├── executor.py     # Vision LLM call via ModelClient — returns raw field dict
    └── verifier.py     # Validates fields, normalises vocabulary, scores confidence
```

The Verifier is **always a separate file** — never merged into the Executor. This makes failure handling a first-class concern, not an afterthought.

#### Backend Services Layout

```
backend/app/services/
├── model_client.py     # ALL OpenRouter calls go through here
└── cache.py            # SHA-256 file cache read/write
```

No agent file should `import openai` directly. All LLM calls go through `model_client.py`.

#### Frontend Component Layout

```
frontend/src/
├── app/
│   ├── layout.tsx          # Root layout
│   └── page.tsx            # Main page (tab navigation)
├── components/
│   ├── ChatPanel.tsx        # Analytics conversation UI
│   ├── UploadPanel.tsx      # Document upload + extraction review
│   ├── DatasetStatus.tsx    # Row count / schema info card
│   └── ErrorToast.tsx       # Structured error display
├── hooks/
│   ├── useAnalytics.ts      # API calls + state for analytics
│   └── useExtraction.ts     # API calls + state for extraction flow
├── lib/
│   └── api.ts               # axios instance with baseURL + interceptors
└── types/
    └── api.ts               # TypeScript types mirroring backend schemas
```

---

### Format Patterns

#### API Response Format

**No envelope wrapper.** Direct response body. `error` field is always present:
- On success: `"error": null`
- On failure: `"error": "error_type_string"`, `"message": "human-readable"`

```python
# Correct — direct response, error null on success
return AnalyticsQueryResponse(answer="...", sql="...", error=None)

# Wrong — do not wrap in data envelope
return {"data": {...}, "status": "ok"}
```

#### JSON Field Naming

`snake_case` throughout — backend to frontend. **No camelCase conversion in axios interceptors.**

```typescript
// Correct
const chartType = response.data.chart_config.type;
const xKey = response.data.chart_config.x_key;

// Wrong — do not transform field names
const chartType = response.data.chartConfig.type;
```

#### FastAPI Error Override

FastAPI's default `HTTPException` returns `{ "detail": "..." }`. Override with the PRD error shape:

```python
# In app/main.py — override FastAPI default error format
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="http_error",
            message=str(exc.detail),
            retry_after=None
        ).model_dump()
    )
```

#### Confidence Enum Values

Always uppercase string literals: `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"NOT_FOUND"`.
Never integers, never lowercase.

```python
class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_FOUND = "NOT_FOUND"
```

#### Date Format

ISO 8601 `YYYY-MM-DD` in all API responses and SQLite storage. No timestamps, no locale-formatted dates.

---

### Process Patterns

#### LLM Call Pattern — ModelClient is Mandatory

```python
# Correct — all LLM calls go through ModelClient
from app.services.model_client import ModelClient
client = ModelClient()
response = await client.complete(model="llama-3.3-70b", messages=[...])

# Wrong — never call OpenRouter directly from agent code
import openai
openai.chat.completions.create(...)
```

`ModelClient` is responsible for: cache lookup, retry with backoff, model fallback, call logging. Bypassing it breaks all four.

#### Cache Key Pattern

```python
import hashlib, json

def make_cache_key(model: str, messages: list, temperature: float) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature},
        sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()
```

`sort_keys=True` is mandatory — key must be deterministic regardless of dict insertion order.

#### Startup Idempotency Pattern

All DB setup in `app/core/database.py` must be safe to run on every deploy:

```python
# Correct — idempotent checks
Base.metadata.create_all(bind=engine)      # SQLAlchemy: no-op if tables exist
if session.query(Shipment).count() == 0:   # Only load CSV if empty
    load_csv_to_db(session)

# Wrong — not idempotent
session.execute(text("CREATE TABLE shipments (...)"))  # Fails if table exists
```

#### Error Handling Pattern — All Routes

Every route handler must use try/except and return `ErrorResponse` — never let FastAPI's unhandled exception handler fire in normal operation:

```python
@router.post("/query")
async def analytics_query(request: AnalyticsQueryRequest):
    try:
        result = await analytics_planner.run(request.question, request.context)
        return AnalyticsQueryResponse(**result, error=None)
    except RateLimitError as e:
        return AnalyticsQueryResponse(error="rate_limit", message=str(e), retry_after=60)
    except LLMParseError as e:
        return AnalyticsQueryResponse(error="parse_error", message=str(e))
    except Exception as e:
        logger.error(f"Unhandled error in analytics_query: {e}")
        return AnalyticsQueryResponse(error="internal_error", message="Unexpected error")
```

#### Frontend Loading State Pattern

Each action in a component gets its own boolean — never share a single `isLoading` across different actions:

```typescript
// Correct — separate booleans per action
const [isQuerying, setIsQuerying] = useState(false);
const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);

// Wrong — ambiguous shared state
const [isLoading, setIsLoading] = useState(false);
```

---

### Enforcement Guidelines

**All agents MUST:**
- Route all LLM calls through `model_client.py` — never import openai directly
- Use the `ErrorResponse` Pydantic model for all error responses — never return raw dicts
- Keep Verifier in a separate file from Executor in both agents
- Use `snake_case` for all JSON field names — no camelCase conversion layer
- Log via Python's `logging` module (INFO/WARNING/ERROR) — never `print()`
- Use `sort_keys=True` when computing cache keys

**Red flags in code review:**
- `import openai` outside of `model_client.py`
- `{"data": ..., "status": ...}` response envelope anywhere
- `isLoading` boolean shared across multiple actions
- `CREATE TABLE` without `IF NOT EXISTS` or SQLAlchemy `create_all`
- Prompt strings hardcoded in agent files (should be in `prompts/`)

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
freightmind/                        # Monorepo root
├── README.md                       # Setup, architecture, demo script
├── docker-compose.yml              # Local dev: frontend + backend together
├── .env.example                    # Documents all required env vars
├── .gitignore
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # uv project config, dependencies
│   ├── uv.lock
│   ├── .env.example
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, lifespan hook, CORS, exception handlers
│   │   │
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic BaseSettings — all env vars
│   │   │   └── database.py         # SQLAlchemy engine, session factory, init_db()
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── shipment.py         # Shipment — maps to shipments table
│   │   │   ├── extracted_document.py
│   │   │   └── extracted_line_item.py
│   │   │
│   │   ├── schemas/                # Pydantic request/response models
│   │   │   ├── common.py           # ErrorResponse, ConfidenceLevel enum (shared)
│   │   │   ├── analytics.py        # AnalyticsQueryRequest/Response, ChartConfig
│   │   │   ├── documents.py        # ExtractionResponse, ConfirmRequest/Response
│   │   │   └── schema_info.py      # SchemaInfoResponse for /api/schema
│   │   │
│   │   ├── agents/
│   │   │   ├── analytics/          # FR1–FR8, FR25–FR28
│   │   │   │   ├── planner.py      # Intent classification, previous_sql context
│   │   │   │   ├── executor.py     # SQL generation via ModelClient
│   │   │   │   └── verifier.py     # SQL safety check, NULL exclusion notes
│   │   │   └── extraction/         # FR9–FR18
│   │   │       ├── planner.py      # Page count, multi-page strategy
│   │   │       ├── executor.py     # Vision extraction via ModelClient (PyMuPDF → image)
│   │   │       └── verifier.py     # Mode/country normalisation, confidence scoring
│   │   │
│   │   ├── services/
│   │   │   ├── model_client.py     # OpenRouter client, cache, retry, fallback, logging
│   │   │   └── cache.py            # SHA-256 file cache read/write
│   │   │
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── analytics.py    # POST /api/analytics/query
│   │   │       ├── documents.py    # POST /extract, /confirm; GET /list
│   │   │       └── system.py       # GET /api/schema, /api/health
│   │   │
│   │   └── prompts/                # FR40 — zero inline prompt strings in agents
│   │       ├── analytics_system.txt       # Analytics agent system prompt
│   │       ├── analytics_sql_gen.txt      # SQL generation instruction + schema context
│   │       ├── extraction_system.txt      # Extraction agent system prompt
│   │       ├── extraction_fields.txt      # 14-field list + extraction instructions
│   │       └── extraction_normalise.txt   # Mode/country vocabulary for normalisation
│   │
│   ├── data/
│   │   └── scms_shipments.csv      # Pre-loaded USAID SCMS dataset (~2MB, committed)
│   │
│   ├── cache/                      # File-based LLM response cache
│   │   └── .gitkeep                # Dir tracked; cache files gitignored
│   │
│   └── scripts/
│       └── load_csv.py             # Standalone dev script: seed DB without running API
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── pnpm-lock.yaml
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── postcss.config.mjs
    ├── .env.example
    │
    └── src/
        ├── app/
        │   ├── layout.tsx          # Root layout, font, metadata
        │   ├── page.tsx            # Tab switcher: Analytics | Documents
        │   └── globals.css         # Tailwind + confidence badge colour vars
        │
        ├── components/
        │   ├── ChatPanel.tsx       # FR1–FR8: input, thread, SQL panel, chart, suggestions
        │   ├── UploadPanel.tsx     # FR9–FR24: drop zone, review table, confirm/cancel
        │   ├── DatasetStatus.tsx   # FR34: row counts + table names from /api/schema
        │   ├── ErrorToast.tsx      # FR29–FR32: structured error + rate limit countdown
        │   ├── SqlDisclosure.tsx   # FR2, FR28: collapsible SQL code block
        │   ├── ConfidenceBadge.tsx # FR13–FR14: HIGH/MEDIUM/LOW/NOT_FOUND badge
        │   ├── ResultTable.tsx     # FR3: column headers, rows, null exclusion note
        │   └── ChartRenderer.tsx  # FR4: Recharts bar/line/pie from chart_config
        │
        ├── hooks/
        │   ├── useAnalytics.ts     # State + API for analytics flow
        │   └── useExtraction.ts    # State + API for extract → review → confirm flow
        │
        ├── lib/
        │   └── api.ts              # axios instance: NEXT_PUBLIC_BACKEND_URL, interceptors
        │
        └── types/
            └── api.ts              # TS interfaces mirroring backend Pydantic schemas
```

---

### Architectural Boundaries

#### API Boundaries

| Boundary | Entry Point | Owns |
|----------|------------|------|
| Analytics boundary | `POST /api/analytics/query` | SQL generation, DB query execution, chart config |
| Extraction boundary | `POST /api/documents/extract` | PDF/image → fields + confidence |
| Confirmation boundary | `POST /api/documents/confirm` | Stores verified extraction to SQLite |
| Transparency boundary | `GET /api/schema`, `GET /api/health` | Read-only introspection |

The frontend never touches SQLite directly. All data access goes through API routes.

#### Component Boundaries

```
ChatPanel ──► useAnalytics ──► lib/api.ts ──► POST /api/analytics/query
                                                     │
                              SqlDisclosure ◄── sql field
                              ChartRenderer ◄── chart_config
                              ResultTable   ◄── data[]

UploadPanel ──► useExtraction ──► lib/api.ts ──► POST /api/documents/extract
                                                        │
                               ConfidenceBadge ◄── fields[].confidence
                               (editable fields) ──► POST /api/documents/confirm
```

`ErrorToast` receives errors from both hooks — wired at `page.tsx` level.

#### Service Boundaries

```
Route handler
    │
    ├──► Planner (intent/strategy — no LLM side effects)
    │        │
    │        └──► Executor (LLM call only — via ModelClient)
    │                 │
    │                 └──► ModelClient ──► cache.py
    │                          │           └──► cache/{hash}.json
    │                          └──► OpenRouter API
    │
    └──► Verifier (validates Executor output — gates side effects)
             │
             └──► database.py (SQLAlchemy session — only if Verifier passes)
```

Nothing writes to the database except through a Verifier pass.

#### Data Boundaries

| Table | Written by | Read by |
|-------|-----------|---------|
| `shipments` | `database.py` startup (CSV load only) | Analytics agent (read-only SQL) |
| `extracted_documents` | Confirm route → SQLAlchemy ORM | Analytics agent (linkage queries) |
| `extracted_line_items` | Confirm route → SQLAlchemy ORM | Analytics agent (linkage queries) |

`shipments` is **read-only at runtime** — enforced by Verifier (NFR8).

---

### Data Flow

**Analytics request path:**
```
User question
  → ChatPanel (React state: question, previousSql)
  → useAnalytics.query()
  → POST /api/analytics/query {question, context: {previous_sql}}
  → AnalyticsPlanner.classify() → structured intent
  → AnalyticsExecutor.generate_sql() → ModelClient → OpenRouter → raw SQL + answer
  → AnalyticsVerifier.validate() → safety check + NULL rule notes
  → database.session.execute(text(sql)) → rows
  → AnalyticsQueryResponse {answer, sql, data, chart_config, null_exclusions}
  → ChatPanel renders: thread + SqlDisclosure + ResultTable + ChartRenderer
```

**Extraction request path:**
```
PDF/image file
  → UploadPanel drag-drop
  → useExtraction.extract()
  → POST /api/documents/extract (multipart)
  → ExtractionPlanner.plan() → page strategy
  → PyMuPDF → page images
  → ExtractionExecutor.extract() → ModelClient → OpenRouter vision → raw field dict
  → ExtractionVerifier.verify() → normalise mode/country + score confidence
  → ExtractionResponse {extraction_id, fields: {field: {value, confidence}}, line_items}
  → UploadPanel renders: review table with ConfidenceBadge per field
  → User edits LOW fields → clicks Confirm
  → POST /api/documents/confirm {extraction_id, corrections}
  → SQLAlchemy ORM writes to extracted_documents + extracted_line_items
```

---

### External Integrations

| Service | Integration Point | File |
|---------|------------------|------|
| OpenRouter (LLM) | All LLM calls | `services/model_client.py` |
| Vercel (frontend deploy) | `git push` → auto-deploy | `frontend/Dockerfile` + Vercel project settings |
| Render (backend deploy) | Docker image from `backend/Dockerfile` | Render service config |
| USAID SCMS dataset | CSV committed to repo | `data/scms_shipments.csv` + `core/database.py` |

---

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:** All technology choices are version-compatible and work together without conflicts. SQLAlchemy 2.x hybrid raw SQL + ORM pattern is well-established. FastAPI lifespan hook runs DB init before first request. Recharts 3.x supports React 19 (bundled with Next.js 16). openai SDK → OpenRouter via base_url override is documented and production-tested.

**Pattern Consistency:** Planner/Executor/Verifier structure is identical across both agents. ErrorResponse Pydantic model is shared via `schemas/common.py`. snake_case JSON throughout with no conversion layer. All LLM calls route through ModelClient. No contradictions between decisions and patterns.

**Structure Alignment:** Every FR category maps to a specific directory. The Verifier-gates-database-writes constraint is enforced by structure — no ORM import in agent files, only in routes (which call verifiers before ORM ops).

---

### Requirements Coverage

**Functional Requirements (44/44 covered):**

| FR Category | Architectural Support |
|-------------|----------------------|
| FR1–FR8: Analytics | `agents/analytics/` + `routes/analytics.py` + `ChatPanel.tsx` |
| FR9–FR18: Extraction | `agents/extraction/` + `routes/documents.py` + `UploadPanel.tsx` |
| FR19–FR24: Review & Confirm | Confirm route + `UploadPanel.tsx` + extraction_id storage pattern (see Gap 1) |
| FR25–FR28: Linkage | Schema-aware analytics prompt includes both tables; UNION SQL via raw execute |
| FR29–FR33: Failure Handling | `model_client.py` retry/fallback + `verifier.py` structured errors + `ErrorToast.tsx` |
| FR34–FR37: Transparency | `routes/system.py` + ModelClient logging + FastAPI auto-docs at `/docs` |
| FR38–FR42: Data Init & Config | `core/database.py` lifespan + `prompts/` directory |
| FR43–FR44: Caching | `services/cache.py` + `BYPASS_CACHE` env var in `core/config.py` |

**Non-Functional Requirements (15/15 covered):**

| NFR | Architectural Support |
|-----|-----------------------|
| NFR1–NFR3: Performance targets | ModelClient cache (< 2s hits); async FastAPI routes (non-blocking LLM calls) |
| NFR4: DB < 100ms | SQLAlchemy + SQLite with indexes defined in `database.py` |
| NFR5: Loading indicator 300ms | Per-action boolean state in React hooks |
| NFR6: Page load < 5s | Vercel static SPA, no SSR |
| NFR7–NFR8: SQL security | `analytics/verifier.py` — regex blocks DROP/DELETE/UPDATE/INSERT/ALTER on shipments |
| NFR9: HTTPS | Enforced by Vercel TLS + Render TLS — no application code needed |
| NFR10: No secrets in repo | `.env.example` committed; `.env` in `.gitignore` |
| NFR11: OpenRouter timeout | `model_client.py` — `httpx_timeout=5.0` on OpenAI client init |
| NFR12: Cold start < 60s | Docker + CSV in repo (no download) + SQLAlchemy `create_all` (< 5s for 10K rows) |
| NFR13: SHA-256 cache key | `cache.py` with `sort_keys=True` |
| NFR14: `/api/health` 500ms | Lightweight route: one DB ping + one OpenRouter reachability check |
| NFR15: PyMuPDF < 5s | Synchronous PDF render in extraction executor before async LLM call |

---

### Gap Analysis & Resolutions

#### Gap 1: extraction_id storage between /extract and /confirm (Resolved)

**Decision:** Store extraction result in `extracted_documents` immediately on `POST /extract` with `confirmed_by_user=0`. The `extraction_id` is the row's `id`.

- `POST /extract` → ExtractionVerifier passes → ORM inserts row with `confirmed_by_user=0` → returns `extraction_id`
- `POST /confirm` → applies user corrections → sets `confirmed_by_user=1`
- User cancels → `DELETE FROM extracted_documents WHERE id = {extraction_id}`

This eliminates in-memory state, survives Render restarts, and is architecturally cleaner than a temporary store. The `confirmed_by_user` field already exists in the schema (DATASET_SCHEMA.md).

**Impact:** `routes/documents.py` confirm/cancel routes use ORM directly — data was already validated on extract, no second Verifier pass needed.

#### Gap 2: uv + Docker build pattern (Resolved)

**Backend Dockerfile (canonical):**
```dockerfile
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY data/ ./data/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile (canonical):**
```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**Required:** Set `output: 'standalone'` in `next.config.ts` for the frontend Dockerfile to work.

---

### Architecture Completeness Checklist

- [x] Project context thoroughly analysed — 44 FRs, 15 NFRs, medium-high complexity
- [x] Scale and complexity assessed — split-stack monorepo, LLM orchestration
- [x] Technical constraints identified — rate limit, ephemeral storage, two LLM modalities
- [x] Cross-cutting concerns mapped — ModelClient, Verifier, ErrorResponse, DB init, Prompt Registry
- [x] Critical decisions documented with versions — Next.js 16.2.1, FastAPI 0.135.2, SQLAlchemy 2.x
- [x] Technology stack fully specified — all 10 tech decisions formalised
- [x] Naming conventions established — DB, API, Python, TypeScript
- [x] Structure patterns defined — Planner/Executor/Verifier, backend/frontend layouts
- [x] Communication patterns specified — LLM call routing, error shape, JSON field casing
- [x] Process patterns documented — cache key, idempotency, route error handling, loading states
- [x] Complete directory structure defined — every file named and annotated with FR coverage
- [x] Component boundaries established — service boundary diagram, data flow paths
- [x] Integration points mapped — OpenRouter, Vercel, Render, SCMS dataset
- [x] Requirements to structure mapping complete — all 44 FRs to specific files
- [x] Gaps identified and resolved — extraction_id storage + uv Docker pattern

---

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Every FR has a named file responsible for it — no ambiguity about where code lives
- The Verifier-gates-database boundary is structurally enforced, not just advisory
- Pre-decided tech stack (TECH_DECISIONS.md) meant zero decisions were re-litigated
- extraction_id storage resolution eliminates the only stateful ambiguity
- Canonical Dockerfiles documented — cold-start reliability is deterministic

**Areas for future enhancement (post-assignment):**
- Replace SQLite with Postgres for multi-writer production use
- Add Redis for session state if Part 2 requires complex conversation history
- Introduce Alembic for DB migrations when schema evolves
- Add structured logging (e.g., structlog) for production observability

---

### Implementation Handoff

**First implementation step:**
```bash
# From repo root
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"
uv init backend --python 3.12
```

**Implementation sequence (dependency order):**
1. Backend foundation: `core/database.py` + ORM models + CSV loader + `/api/health`
2. Model Abstraction Layer: `services/model_client.py` + `services/cache.py`
3. Analytics agent: `agents/analytics/` + `routes/analytics.py`
4. Extraction agent: `agents/extraction/` + `routes/documents.py`
5. Frontend: `ChatPanel` → `UploadPanel` → `ChartRenderer` + `ConfidenceBadge`
6. Integration: linkage queries + end-to-end smoke test
7. Docker + deployment: Dockerfiles + `docker-compose.yml` + Vercel + Render

**All agents implementing this architecture must:**
- Route LLM calls through `model_client.py` only
- Use `ErrorResponse` from `schemas/common.py` for all error returns
- Never hardcode prompts — load from `prompts/` directory
- Follow naming patterns exactly as specified in Implementation Patterns section
- Refer to this document for all architectural questions before making new decisions
