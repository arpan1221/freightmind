---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete'
completedAt: '2026-03-30'
inputDocuments: ['_bmad-output/planning-artifacts/prd.md', '_bmad-output/planning-artifacts/architecture.md']
---

# FreightMind - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for FreightMind, decomposing the requirements from the PRD and Architecture into implementable stories organised by user value.

---

## Requirements Inventory

### Functional Requirements

FR1: User can submit a natural language question about shipment data and receive a data-backed text answer
FR2: User can view the exact SQL query used to produce any analytics response
FR3: User can view analytics query results as a structured data table with column headers and row counts
FR4: User can view at least one chart visualisation (bar, line, or pie) for quantitative analytics results
FR5: User can submit a follow-up question that refines a previous query result by filter, grouping, or time window
FR6: System can detect when a question references data not present in the dataset and returns a clear explanation of what data is available
FR7: System surfaces the count of records excluded from a query due to NULL values in the response text
FR8: User can view suggested follow-up questions after receiving an analytics response
FR9: User can upload a PDF document for structured field extraction
FR10: User can upload an image file (PNG, JPG, JPEG) for structured field extraction
FR11: System extracts 14 defined structured fields from an uploaded freight document using a vision-capable model
FR12: System extracts line items (description, quantity, unit price, total price) from an uploaded document
FR13: System assigns a confidence level (HIGH, MEDIUM, LOW, or NOT_FOUND) to each extracted field
FR14: System visually distinguishes LOW confidence and NOT_FOUND fields from HIGH/MEDIUM confidence fields in the extraction review
FR15: System normalises extracted shipment mode values to accepted vocabulary (Air, Ocean, Truck, Air Charter) before presenting for review
FR16: System normalises extracted country names to dataset vocabulary before presenting for review
FR17: System normalises extracted dates to ISO 8601 format (YYYY-MM-DD) before presenting for review
FR18: System normalises extracted weight values to kilograms before presenting for review
FR19: User can review all extracted fields before any data is stored
FR20: User can edit any extracted field value in the review panel before confirming
FR21: User can confirm a reviewed extraction to persist it to the shared data store
FR22: User can cancel an extraction without storing any data
FR23: System stores confirmed extractions in a queryable format accessible to the analytics layer
FR24: User can view a list of all previously confirmed extracted documents
FR25: User can ask natural language questions that query extracted document data using the same analytics interface as historical data
FR26: System can return answers that combine data from both historical shipment records and confirmed extracted documents in a single response
FR27: System can execute cross-table queries spanning shipments and extracted_documents tables
FR28: User can view the SQL for any linkage query, showing both source tables referenced
FR29: System returns a structured error response when the LLM produces malformed or unparseable output, without crashing
FR30: System retries a failed LLM call at least once with a corrective instruction appended before surfacing an error to the user
FR31: System returns a structured error response when an API rate limit is reached, including the duration before the next retry is possible
FR32: System returns a structured error response when a user question produces invalid or unsafe SQL, including the failed query for transparency
FR33: System automatically switches to a fallback model when the primary model is unavailable or fails after retries
FR34: System exposes the complete database schema, table row counts, and sample column values via a dedicated read-only endpoint
FR35: System provides a health check endpoint reporting database connection status and model reachability
FR36: System auto-generates and exposes interactive API documentation accessible without authentication
FR37: System logs each LLM API call with model name, cache hit/miss status, and retry count
FR38: System automatically loads the SCMS CSV dataset into the database on startup when the shipments table is empty
FR39: System automatically creates all required database tables and indexes on startup if they do not exist
FR40: All LLM prompt templates are stored in dedicated configuration files separate from business logic code
FR41: The analytics agent module can be invoked and tested independently without the vision extraction module
FR42: The vision extraction module can be invoked and tested independently without the analytics agent module
FR43: System caches LLM API responses keyed by a hash of the request payload to avoid redundant API calls during development
FR44: System provides an environment-variable-controlled option to bypass the response cache for fresh API calls

---

### NonFunctional Requirements

NFR1: Analytics query responses (cache miss) must complete within 15 seconds under normal network conditions
NFR2: Document extraction responses (cache miss) must complete within 30 seconds for single-page PDFs
NFR3: All cached responses (analytics or extraction) must be returned within 2 seconds
NFR4: SQLite queries against the shipments table must complete within 100ms for all indexed columns
NFR5: The frontend must display a loading indicator within 300ms of any user-initiated action
NFR6: The Vercel frontend must load and render the initial SPA within 5 seconds on a cold start
NFR7: All SQL executed against the database must be generated by the LLM and validated by the Verifier layer — no raw user input is interpolated directly into SQL strings
NFR8: The Verifier layer must reject any generated SQL containing DROP, DELETE, UPDATE, INSERT, or ALTER statements targeting the shipments table
NFR9: All frontend-to-backend communication must occur over HTTPS
NFR10: API keys and secrets must be stored as environment variables only — never committed to the repository
NFR11: The system must handle OpenRouter API unavailability gracefully — returning a structured error response within 5 seconds of connection timeout
NFR12: The backend must initialise successfully from a cold Render deploy within 60 seconds, including CSV load and schema creation
NFR13: The response cache must be keyed by a SHA-256 hash of the full request payload (model + messages + temperature)
NFR14: The /api/health endpoint must respond within 500ms and accurately reflect database connectivity and OpenRouter reachability
NFR15: PyMuPDF PDF-to-image conversion must complete within 5 seconds for documents up to 10 pages before passing to the vision model

---

### Additional Requirements

From Architecture decisions — these affect implementation scope and sequencing:

- **Starter init:** `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --turbopack --import-alias "@/*"` and `uv init backend --python 3.12` are the project scaffold commands — Epic 1 Story 1 is project initialisation
- **SQLAlchemy hybrid:** ORM for table creation, CSV loading, and document writes; raw `session.execute(text(sql))` for all LLM-generated analytics queries
- **extraction_id storage:** `POST /extract` stores row with `confirmed_by_user=0` immediately; `POST /confirm` sets it to 1; cancel deletes the row — no in-memory temp state
- **Docker everywhere:** Backend Dockerfile uses `ghcr.io/astral-sh/uv:latest` COPY pattern; Frontend Dockerfile uses multi-stage build with `output: 'standalone'` in next.config.ts; `docker-compose.yml` at root wires both
- **ModelClient is mandatory gateway:** All LLM calls must go through `services/model_client.py` — handles cache, retry (1s→2s→4s), fallback model, call logging
- **Verifier gates all DB writes:** No route may write to SQLite without a Verifier pass first
- **CORS wildcard:** `*` origin for POC; configured in `app/main.py`
- **FastAPI error override:** Default `HTTPException` handler overridden to return `ErrorResponse` shape (not `{"detail": ...}`)
- **Prompt registry:** All prompts in `backend/app/prompts/*.txt` — zero inline strings in agent code
- **`BYPASS_CACHE` env var:** Controlled via `core/config.py` Pydantic BaseSettings

---

### UX Design Requirements

No standalone UX design document exists. Frontend requirements are specified inline in the PRD and Architecture:

- UX-DR1: Chat panel with message thread, input box, loading spinner, collapsible SQL disclosure block, result table, chart area, and follow-up suggestions list
- UX-DR2: Upload panel with drag-and-drop drop zone, file preview, extraction review table with editable fields and per-field confidence badges, and confirm/cancel buttons
- UX-DR3: Dataset status card showing row counts and table names (sourced from /api/schema)
- UX-DR4: Error toast component with structured error text and countdown timer when retry_after is present
- UX-DR5: Confidence badges: HIGH=green, MEDIUM=amber, LOW=red, NOT_FOUND=red with visual distinction from LOW
- UX-DR6: SQL disclosure block is collapsible — hidden by default, expandable on click
- UX-DR7: Loading indicator must appear within 300ms of any user action (per NFR5); separate isLoading booleans per action (isQuerying, isExtracting, isConfirming)

---

### FR Coverage Map

| Requirement | Epic |
|-------------|------|
| FR1 – NL question → text answer | Epic 2: Analytics Agent |
| FR2 – Show generated SQL | Epic 2: Analytics Agent |
| FR3 – Result table with headers + row count | Epic 2: Analytics Agent |
| FR4 – Chart visualisation (bar/line/pie) | Epic 2: Analytics Agent |
| FR5 – Follow-up question refines previous query | Epic 2: Analytics Agent |
| FR6 – Detect out-of-scope questions | Epic 2: Analytics Agent |
| FR7 – Surface NULL-excluded record count | Epic 2: Analytics Agent |
| FR8 – Suggested follow-up questions | Epic 2: Analytics Agent |
| FR9 – Upload PDF for extraction | Epic 3: Document Processing |
| FR10 – Upload image (PNG/JPG/JPEG) for extraction | Epic 3: Document Processing |
| FR11 – Extract 14 structured fields via vision model | Epic 3: Document Processing |
| FR12 – Extract line items from document | Epic 3: Document Processing |
| FR13 – Assign confidence level per field | Epic 3: Document Processing |
| FR14 – Visual distinction for LOW/NOT_FOUND fields | Epic 3: Document Processing |
| FR15 – Normalise shipment mode to vocabulary | Epic 3: Document Processing |
| FR16 – Normalise country names to dataset vocabulary | Epic 3: Document Processing |
| FR17 – Normalise dates to ISO 8601 | Epic 3: Document Processing |
| FR18 – Normalise weights to kg | Epic 3: Document Processing |
| FR19 – Review extracted fields before storage | Epic 3: Document Processing |
| FR20 – Edit any field in review panel | Epic 3: Document Processing |
| FR21 – Confirm extraction → persist to store | Epic 3: Document Processing |
| FR22 – Cancel extraction without storing | Epic 3: Document Processing |
| FR23 – Store confirmed extractions in queryable format | Epic 3: Document Processing |
| FR24 – View list of confirmed extracted documents | Epic 3: Document Processing |
| FR25 – Query extracted document data via analytics interface | Epic 4: End-to-End Linkage |
| FR26 – Combined answers across both data sources | Epic 4: End-to-End Linkage |
| FR27 – Cross-table queries (shipments + extracted_documents) | Epic 4: End-to-End Linkage |
| FR28 – View SQL showing both source tables | Epic 4: End-to-End Linkage |
| FR29 – Structured error on malformed LLM output | Epic 5: Failure Handling |
| FR30 – Retry failed LLM call with corrective instruction | Epic 5: Failure Handling |
| FR31 – Structured error on rate limit with retry_after | Epic 5: Failure Handling |
| FR32 – Structured error on invalid/unsafe SQL | Epic 5: Failure Handling |
| FR33 – Auto-switch to fallback model on primary failure | Epic 5: Failure Handling |
| FR34 – Schema endpoint (tables, row counts, sample values) | Epic 2: Analytics Agent |
| FR35 – Health check endpoint (DB + model reachability) | Epic 1: Foundation |
| FR36 – Auto-generated interactive API docs | Epic 2: Analytics Agent |
| FR37 – LLM call logging (model, cache hit/miss, retry count) | Epic 2: Analytics Agent |
| FR38 – Auto-load SCMS CSV on startup when table empty | Epic 1: Foundation |
| FR39 – Auto-create DB tables and indexes on startup | Epic 1: Foundation |
| FR40 – Prompt templates in config files (not inline) | Epic 1: Foundation |
| FR41 – Analytics agent independently invocable/testable | Epic 2: Analytics Agent |
| FR42 – Vision extraction independently invocable/testable | Epic 3: Document Processing |
| FR43 – File-based LLM response cache (SHA-256 hash key) | Epic 1: Foundation |
| FR44 – BYPASS_CACHE env var to skip cache | Epic 1: Foundation |
| NFR1 – Analytics response < 15s (cache miss) | Epic 2: Analytics Agent |
| NFR2 – Extraction response < 30s single-page PDF | Epic 3: Document Processing |
| NFR3 – Cached responses < 2s | Epic 1: Foundation |
| NFR4 – SQLite queries < 100ms on indexed columns | Epic 1: Foundation |
| NFR5 – Loading indicator within 300ms | Epic 2 + 3: Frontend UX |
| NFR6 – SPA loads within 5s cold start | Epic 6: Deployment |
| NFR7 – No raw user input interpolated into SQL | Epic 2: Analytics Agent |
| NFR8 – Verifier rejects DROP/DELETE/UPDATE/INSERT/ALTER | Epic 2: Analytics Agent |
| NFR9 – All comms over HTTPS | Epic 6: Deployment |
| NFR10 – API keys in env vars only | Epic 1: Foundation |
| NFR11 – OpenRouter unavailability handled within 5s | Epic 5: Failure Handling |
| NFR12 – Cold Render deploy init within 60s | Epic 6: Deployment |
| NFR13 – Cache keyed by SHA-256 of full request payload | Epic 1: Foundation |
| NFR14 – /api/health responds within 500ms | Epic 1: Foundation |
| NFR15 – PyMuPDF PDF→image conversion < 5s (≤10 pages) | Epic 3: Document Processing |
| UX-DR1 – Chat panel layout | Epic 2: Analytics Agent |
| UX-DR2 – Upload panel layout + confidence badges | Epic 3: Document Processing |
| UX-DR3 – Dataset status card (/api/schema sourced) | Epic 2: Analytics Agent |
| UX-DR4 – Error toast with countdown timer | Epic 5: Failure Handling |
| UX-DR5 – Confidence badge colours (HIGH/MEDIUM/LOW/NOT_FOUND) | Epic 3: Document Processing |
| UX-DR6 – SQL disclosure block collapsible, hidden by default | Epic 2: Analytics Agent |
| UX-DR7 – Separate isLoading booleans per action | Epic 2 + 3: Frontend UX |

**Coverage: 44/44 FRs + 15 NFRs + 7 UX-DRs — all mapped.**

---

## Epic List

| # | Epic | Goal | FRs Covered | Depends On |
|---|------|------|-------------|------------|
| 1 | Project Foundation & Running System | Running backend with health check, DB init, CSV load, prompt config, and response cache | FR35, FR38, FR39, FR40, FR43, FR44 + NFR3, NFR4, NFR10, NFR13, NFR14 | — |
| 2 | Analytics Agent — Natural Language Queries | User can ask NL questions and receive SQL-backed answers with table, chart, follow-ups, and SQL transparency | FR1–FR8, FR34, FR36, FR37, FR41 + NFR1, NFR7, NFR8 + UX-DR1, UX-DR3, UX-DR6, UX-DR7 | Epic 1 |
| 3 | Document Processing — Extract, Review & Confirm | User can upload freight docs, review extracted fields with confidence, edit and confirm or cancel | FR9–FR24, FR42 + NFR2, NFR15 + UX-DR2, UX-DR5, UX-DR7 | Epic 1 |
| 4 | End-to-End Data Linkage | Confirmed extractions are queryable via the analytics interface; UNION/JOIN queries span both tables | FR25–FR28 | Epics 2 + 3 |
| 5 | Failure Handling & Resilience | All failure paths (malformed LLM output, invalid SQL, rate limits, model fallback) return structured errors | FR29–FR33 + NFR11 + UX-DR4 | Epics 2 + 3 |
| 6 | Deployment & Demo Readiness | Docker Compose, Vercel + Render deploy, README, demo invoices, demo script | NFR6, NFR9, NFR12 | Epics 1–5 |

---

## Epic 1: Project Foundation & Running System

**Goal:** A cold-start runnable system — backend initialises, DB schema exists, SCMS CSV loads, health check passes, prompt registry in place, response cache operational. All other epics depend on this.

**FRs:** FR35, FR38, FR39, FR40, FR43, FR44
**NFRs:** NFR3, NFR4, NFR10, NFR13, NFR14

---

### Story 1.1: Scaffold backend project with uv, FastAPI, and Docker

As a developer,
I want a runnable FastAPI backend with uv dependency management, a Docker image, and environment variable configuration,
So that I have a deployable foundation on which all agents and routes are built.

**Acceptance Criteria:**

**Given** the developer clones the repo and has Docker installed
**When** they run `docker-compose up backend`
**Then** the FastAPI server starts on port 8000 with no errors
**And** `GET /docs` returns the auto-generated OpenAPI UI (FR36)
**And** no API keys or secrets appear in any committed file (NFR10)

**Given** a `.env` file is present with `OPENROUTER_API_KEY` set
**When** the backend starts
**Then** `core/config.py` loads the value via Pydantic `BaseSettings` without crashing

**Given** `BYPASS_CACHE=true` is set in the environment
**When** the backend starts
**Then** `core/config.py` exposes `bypass_cache=True` and the value is accessible to `ModelClient` (FR44)

---

### Story 1.2: Auto-create database schema and indexes on startup

As a developer,
I want all required SQLite tables and indexes created automatically when the backend starts,
So that no manual migration step is needed on a fresh deploy.

**Acceptance Criteria:**

**Given** the backend starts against a fresh SQLite file (no existing tables)
**When** the startup event fires
**Then** `shipments`, `extracted_documents`, and `extracted_line_items` tables are created with all columns defined in the architecture schema
**And** indexes are created on `shipments.shipment_mode`, `shipments.country`, and `shipments.po_sent_to_vendor_date` (NFR4)
**And** the operation completes without error

**Given** the backend restarts against an existing SQLite file with tables already present
**When** the startup event fires
**Then** no error is raised and no duplicate tables are created (`checkfirst=True` / `IF NOT EXISTS`)

---

### Story 1.3: Auto-load SCMS CSV into shipments table on cold start

As a logistics analyst,
I want 10,324 shipment records from the SCMS dataset available immediately after the system starts,
So that I can query historical freight data without any manual data import step.

**Acceptance Criteria:**

**Given** the `shipments` table is empty and `backend/data/SCMS_Delivery_History_Dataset.csv` is present
**When** the startup event fires (after schema creation in Story 1.2)
**Then** all 10,324 rows are bulk-loaded into the `shipments` table
**And** sentinel values (`-49`) for cost and weight columns are loaded as-is (not converted at this stage — handled in query layer)
**And** the load completes within 60 seconds on a cold Render deploy (NFR12)

**Given** the `shipments` table already contains rows
**When** the backend restarts
**Then** no rows are inserted (idempotent — load is skipped entirely)

---

### Story 1.4: Health check endpoint

As a developer (and evaluator),
I want a `/api/health` endpoint that reports database connectivity and model reachability,
So that I can verify the system is operational without running a full query.

**Acceptance Criteria:**

**Given** the database file is accessible and the OpenRouter API key is set
**When** `GET /api/health` is called
**Then** the response returns HTTP 200 with `{"status": "ok", "database": "connected", "model": "reachable"}` within 500ms (NFR14)

**Given** the SQLite file is missing or unreadable
**When** `GET /api/health` is called
**Then** the response returns HTTP 200 with `{"status": "degraded", "database": "error", "model": "reachable"}` (health endpoint never returns 5xx)

**Given** the OpenRouter API is unreachable (e.g., network timeout)
**When** `GET /api/health` is called
**Then** the response includes `"model": "unreachable"` and still returns within 500ms

---

### Story 1.5: Prompt registry — all prompt templates as .txt files

As a developer,
I want all LLM prompt templates stored as `.txt` files in `backend/app/prompts/`,
So that prompts can be updated without touching business logic code.

**Acceptance Criteria:**

**Given** the backend starts
**When** any agent loads a prompt template
**Then** it reads from a `.txt` file in `app/prompts/` — no inline f-string prompt exists in agent code (FR40)

**Given** a `.txt` prompt file is missing at startup
**When** any agent attempts to load it
**Then** a clear `FileNotFoundError` is raised with the missing file path (fail-fast)

**Given** the prompt files exist on disk
**When** a developer inspects `app/prompts/`
**Then** they find at minimum: `analytics_planner.txt`, `analytics_executor.txt`, `analytics_verifier.txt`, `extraction_executor.txt`, `extraction_verifier.txt`

---

### Story 1.6: ModelClient with file-based SHA-256 response cache

As a developer,
I want a `ModelClient` that is the sole gateway for all LLM API calls, with a file-based SHA-256 response cache and configurable bypass,
So that LLM API calls are reused during development to preserve the 50 req/day free tier quota.

**Acceptance Criteria:**

**Given** `ModelClient.call(model, messages, temperature)` is called with a payload
**When** a cached response exists for the SHA-256 hash of `sort_keys=True` JSON serialisation of `{model, messages, temperature}` (NFR13)
**Then** the cached response is returned within 2 seconds (NFR3)
**And** the log entry shows `cache_hit=True`, `model_name`, `retry_count` (FR37)

**Given** no cached response exists
**When** `ModelClient.call()` is invoked
**Then** the live OpenRouter API is called and the response is written to the cache file
**And** the log entry shows `cache_hit=False`, `model_name`, and `retry_count=0` (FR37)

**Given** `BYPASS_CACHE=true` is set
**When** `ModelClient.call()` is invoked
**Then** the cache is skipped entirely and a live API call is made regardless of cached state (FR44)

**Given** any agent module imports LLM functionality
**When** the code is inspected
**Then** it imports `ModelClient` from `services/model_client.py` — no direct `openai` or `httpx` LLM calls exist outside `model_client.py`

---

### Story 1.7: Scaffold frontend project with Next.js, TypeScript, Tailwind, and Docker

As a developer,
I want a Next.js 16 frontend with TypeScript, Tailwind, App Router, and a multi-stage Docker image,
So that the UI scaffold is in place and runnable locally via Docker Compose.

**Acceptance Criteria:**

**Given** the developer runs `docker-compose up frontend`
**When** the build completes
**Then** the Next.js app is served on port 3000 with no build errors
**And** `next.config.ts` includes `output: 'standalone'` for the multi-stage Docker build

**Given** the developer opens `http://localhost:3000`
**When** the page loads
**Then** the initial SPA renders within 5 seconds on a cold start (NFR6)
**And** the page displays a placeholder layout with chat panel and upload panel areas

**Given** the frontend Dockerfile is inspected
**When** built
**Then** it uses a two-stage build: `node:22-alpine` builder stage + `node:22-alpine` runner stage copying `.next/standalone`

---

## Epic 2: Analytics Agent — Natural Language Queries

**Goal:** User can type a natural language question and receive a SQL-backed text answer with generated SQL visible, a result table, a chart, suggested follow-ups, and honest handling of unanswerable questions.

**FRs:** FR1–FR8, FR34, FR36, FR37, FR41
**NFRs:** NFR1, NFR7, NFR8
**UX:** UX-DR1, UX-DR3, UX-DR6, UX-DR7

---

### Story 2.1: Analytics pipeline — POST /api/query (Planner → Executor → Verifier)

As a logistics analyst,
I want to submit a natural language question via `POST /api/query` and receive a text answer backed by a SQL query executed against the shipments dataset,
So that I can get data-driven answers without writing SQL.

**Acceptance Criteria:**

**Given** the backend is running with the SCMS dataset loaded
**When** `POST /api/query` is called with `{"question": "What is the average freight cost per shipment mode?"}`
**Then** the response returns HTTP 200 with a JSON body containing `answer`, `sql`, `columns`, `rows`, and `row_count` (FR1, FR2, FR3)
**And** the response arrives within 15 seconds on a cache miss (NFR1)

**Given** the Verifier receives generated SQL containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, or `ALTER` targeting `shipments`
**When** it validates the SQL
**Then** the query is rejected and a structured error response is returned — the SQL is never executed (NFR8)

**Given** the response is constructed
**When** the SQL is executed
**Then** it uses `session.execute(text(generated_sql))` — no ORM query builder is used for analytics execution

**Given** no raw user input is present in the executed SQL string
**When** the code is inspected
**Then** all SQL is generated by the LLM and passed through the Verifier — no string interpolation of `question` into SQL (NFR7)

---

### Story 2.2: Out-of-scope detection, NULL surfacing, and follow-up suggestions

As a logistics analyst,
I want the system to tell me clearly when my question can't be answered from the data, report how many records were excluded due to NULL values, and suggest relevant follow-up questions,
So that I know the limits of the data and how to explore further.

**Acceptance Criteria:**

**Given** a user asks a question referencing data not in the dataset (e.g., "What is the carbon footprint of each shipment?")
**When** the analytics pipeline processes the question
**Then** the response `answer` explains what data is available and why the question can't be answered — no fabricated result is returned (FR6)

**Given** a query filters on a column containing sentinel values (`-49`) used as NULLs
**When** the response is constructed
**Then** the `answer` text includes a sentence noting how many records were excluded due to NULL/sentinel values in the relevant column (FR7)

**Given** a successful query completes
**When** the response is returned
**Then** it includes a `suggested_questions` array with 2–3 complete natural language follow-up questions relevant to the result (FR8)

---

### Story 2.3: Chart configuration generation

As a logistics analyst,
I want the analytics response to include a chart configuration when the result is quantitative,
So that I can see a visual representation of the data without configuring a chart manually.

**Acceptance Criteria:**

**Given** a query returns quantitative results with a categorical dimension (e.g., cost by shipment mode)
**When** the response is constructed
**Then** it includes a `chart_config` object with `type` (one of `bar`, `line`, `pie`), `x_key`, and `y_key` (FR4)

**Given** the `chart_config` is passed to the frontend
**When** the chart component renders
**Then** a bar, line, or pie chart is displayed using Recharts with the correct data mapping

**Given** a query returns non-quantitative results (e.g., a list of vendor names)
**When** the response is constructed
**Then** `chart_config` is `null` — no chart is rendered

---

### Story 2.4: Stateless follow-up query with previous SQL context

As a logistics analyst,
I want to ask a follow-up question that refines a previous query by adding a filter, changing a grouping, or adjusting a time window,
So that I can iteratively explore data without restarting from scratch.

**Acceptance Criteria:**

**Given** a previous query returned SQL and results
**When** `POST /api/query` is called with `{"question": "Filter that to Air shipments only", "previous_sql": "<prior SQL>"}`
**Then** the Planner uses `previous_sql` as context to generate a refined query
**And** the response returns refined results with updated SQL, table, and chart (FR5)

**Given** `previous_sql` is omitted from the request
**When** `POST /api/query` is called
**Then** the system treats it as a fresh query with no prior context (graceful null handling)

**Given** the backend processes the follow-up
**When** the code is inspected
**Then** no server-side session state is maintained — `previous_sql` in the request body is the sole source of context

---

### Story 2.5: Schema endpoint — GET /api/schema

As a developer (and evaluator),
I want a `GET /api/schema` endpoint that exposes all table names, row counts, column names, and sample values,
So that I can inspect what data is available and verify the system loaded correctly.

**Acceptance Criteria:**

**Given** the database is populated with the SCMS dataset
**When** `GET /api/schema` is called
**Then** the response returns a JSON object listing each table name, its row count, all column names, and up to 3 sample distinct values per column (FR34)
**And** the response is read-only — no writes are triggered

**Given** the schema endpoint is accessed
**When** the FastAPI docs at `/docs` are opened
**Then** the endpoint appears in the auto-generated Swagger UI (FR36)

---

### Story 2.6: Chat panel UI — full analytics interaction

As a logistics analyst,
I want a chat panel in the frontend where I can type questions and see the AI's answer with the SQL used, a data table, a chart, and suggested follow-ups,
So that I have a complete self-service analytics interface.

**Acceptance Criteria:**

**Given** the user types a question and submits it
**When** the request is in flight
**Then** a loading spinner appears within 300ms of submission using an `isQuerying` boolean (NFR5, UX-DR7)

**Given** a successful response arrives
**When** it is rendered
**Then** the chat panel displays: the text answer, a collapsible SQL block (collapsed by default, expandable on click), a data table with column headers and row count, a chart (if `chart_config` is not null), and suggested follow-up question chips (UX-DR1, UX-DR6, FR2, FR3, FR4, FR8)

**Given** the user clicks a suggested follow-up chip
**When** it is clicked
**Then** the chip's text is submitted as the next question with `previous_sql` populated from the prior response

**Given** the user opens `http://localhost:3000`
**When** the page loads
**Then** a dataset status card shows table names and row counts sourced from `GET /api/schema` (UX-DR3)

---

### Story 2.7: Analytics agent standalone invocability

As a developer,
I want to invoke and test the analytics agent independently without starting the vision extraction module,
So that I can develop and debug the analytics pipeline in isolation.

**Acceptance Criteria:**

**Given** only the analytics-related modules are imported
**When** `POST /api/query` is called
**Then** it processes successfully without any import of vision extraction modules (FR41)

**Given** the vision extraction route files are absent
**When** the analytics agent is invoked directly
**Then** it runs without import errors

---

## Epic 3: Document Processing — Extract, Review & Confirm

**Goal:** User can upload a freight invoice (PDF or image), review extracted fields with per-field confidence scores, edit any field, then confirm to persist or cancel to discard. No data is stored without user review.

**FRs:** FR9–FR24, FR42
**NFRs:** NFR2, NFR15
**UX:** UX-DR2, UX-DR5, UX-DR7

---

### Story 3.1: File upload endpoint — POST /extract

As a logistics operations analyst,
I want to upload a PDF or image of a freight invoice to `POST /extract` and receive structured extracted fields in the response,
So that I can review what the AI extracted before deciding to save it.

**Acceptance Criteria:**

**Given** a valid single-page PDF freight invoice is uploaded to `POST /extract`
**When** the endpoint processes the file
**Then** it converts the PDF to an image using PyMuPDF within 5 seconds (NFR15)
**And** passes the image to the vision model (Qwen3 VL 235B via OpenRouter)
**And** returns a response containing an `extraction_id`, all 14 structured fields, and extracted line items (FR9, FR11, FR12)
**And** the full response arrives within 30 seconds (NFR2)
**And** a row is inserted into `extracted_documents` with `confirmed_by_user=0` using the returned `extraction_id`

**Given** a PNG, JPG, or JPEG image file is uploaded to `POST /extract`
**When** the endpoint processes the file
**Then** it passes the image directly to the vision model (no PDF conversion step) and returns the same structured response (FR10)

**Given** an unsupported file type is uploaded (e.g., `.xlsx`)
**When** the endpoint validates the upload
**Then** it returns a structured error response with a clear message about accepted formats — no crash

---

### Story 3.2: Normalisation layer — mode, country, date, and weight

As a logistics operations analyst,
I want extracted values normalised to standard vocabulary before I review them,
So that I see clean, consistent data rather than raw OCR variants.

**Acceptance Criteria:**

**Given** the vision model returns a shipment mode value (e.g., "AIR FREIGHT", "by air", "Air-charter")
**When** normalisation is applied
**Then** the value is mapped to one of: `Air`, `Ocean`, `Truck`, or `Air Charter` — unrecognised values receive `NOT_FOUND` confidence (FR15)

**Given** the vision model returns a country name (e.g., "DRC", "Congo", "Democratic Republic of the Congo")
**When** normalisation is applied
**Then** the value is mapped to the corresponding dataset vocabulary country name (FR16)

**Given** the vision model returns a date in any format (e.g., "March 5, 2024", "05/03/24")
**When** normalisation is applied
**Then** the value is stored and displayed as `YYYY-MM-DD` ISO 8601 format (FR17)

**Given** the vision model returns a weight with units (e.g., "250 lbs", "0.25 tonnes")
**When** normalisation is applied
**Then** the value is converted to kilograms and stored as a numeric value (FR18)

---

### Story 3.3: Confidence scoring per field

As a logistics operations analyst,
I want each extracted field to carry a confidence level of HIGH, MEDIUM, LOW, or NOT_FOUND,
So that I can immediately see which fields need my attention before confirming.

**Acceptance Criteria:**

**Given** the vision model returns extracted fields with confidence scores
**When** the response is assembled
**Then** each of the 14 fields and each line item field has a `confidence` value of `HIGH`, `MEDIUM`, `LOW`, or `NOT_FOUND` (FR13)

**Given** a field could not be found in the document
**When** the response is assembled
**Then** the field value is `null` and confidence is `NOT_FOUND`

**Given** a field has `LOW` or `NOT_FOUND` confidence
**When** the extraction response is inspected
**Then** a `low_confidence_fields` list in the response enumerates those field names for the frontend to flag (FR14)

---

### Story 3.4: Confirm endpoint — POST /confirm/{extraction_id}

As a logistics operations analyst,
I want to confirm a reviewed extraction so it is persisted as a verified record in the data store,
So that the data becomes available for analytics queries.

**Acceptance Criteria:**

**Given** a valid `extraction_id` exists in `extracted_documents` with `confirmed_by_user=0`
**When** `POST /confirm/{extraction_id}` is called with any edited field values in the request body
**Then** the `extracted_documents` row is updated: edited fields are applied and `confirmed_by_user` is set to `1` (FR21)
**And** the response returns HTTP 200 with the confirmed record

**Given** `POST /confirm` is called before a Verifier pass
**When** the code is inspected
**Then** the Verifier validates the field values before the write is committed — no route writes to SQLite without a Verifier pass

**Given** the confirmed record is stored
**When** a subsequent `GET /api/schema` is called
**Then** the `extracted_documents` row count has increased by 1 (FR23)

---

### Story 3.5: Cancel endpoint — DELETE /extract/{extraction_id}

As a logistics operations analyst,
I want to cancel an extraction review so no data is stored,
So that I can discard a bad upload without polluting the database.

**Acceptance Criteria:**

**Given** a valid `extraction_id` exists with `confirmed_by_user=0`
**When** `DELETE /extract/{extraction_id}` is called
**Then** the row is deleted from `extracted_documents` and associated `extracted_line_items` rows are also deleted (FR22)
**And** the response returns HTTP 200 confirming deletion

**Given** an unknown `extraction_id` is provided
**When** `DELETE /extract/{extraction_id}` is called
**Then** the response returns a structured error with HTTP 404 — no crash

---

### Story 3.6: Extracted documents list — GET /extractions

As a logistics operations analyst,
I want to view a list of all previously confirmed extracted documents,
So that I can see what invoice data has been added to the system.

**Acceptance Criteria:**

**Given** at least one confirmed extraction exists in the database
**When** `GET /extractions` is called
**Then** the response returns a list of records with `confirmed_by_user=1`, including `extraction_id`, `filename`, `extracted_at`, and key field values (FR24)

**Given** no confirmed extractions exist
**When** `GET /extractions` is called
**Then** the response returns an empty list — not an error

---

### Story 3.7: Upload panel UI — drag-and-drop, review table, confidence badges, edit, confirm/cancel

As a logistics operations analyst,
I want an upload panel in the frontend where I can drop a freight invoice, review extracted fields with colour-coded confidence badges, edit any field, and confirm or cancel,
So that I have full control over what data enters the system.

**Acceptance Criteria:**

**Given** the user opens the upload panel
**When** they drag a PDF or image onto the drop zone
**Then** a file preview appears and the file is submitted to `POST /extract`
**And** an `isExtracting` loading spinner appears within 300ms of drop (NFR5, UX-DR7)

**Given** the extraction response arrives
**When** it is rendered
**Then** a review table displays all 14 extracted fields with their values and confidence badges (UX-DR2, UX-DR5)
**And** HIGH confidence badges are green, MEDIUM are amber, LOW are red, NOT_FOUND are red with a distinct "NOT FOUND" label — visually distinguishable from LOW (FR14, UX-DR5)
**And** line items are displayed in a sub-table with description, quantity, unit price, and total price

**Given** the user clicks a field value in the review table
**When** they edit it
**Then** the field becomes an inline editable input — the edited value is included in the confirm request body (FR20)

**Given** the user clicks Confirm
**When** the `isConfirming` spinner resolves
**Then** `POST /confirm/{extraction_id}` is called with any edited fields, the UI shows a success state, and the review table is cleared (FR21, UX-DR7)

**Given** the user clicks Cancel
**When** the action completes
**Then** `DELETE /extract/{extraction_id}` is called and the review table is cleared with no data saved (FR22)

---

### Story 3.8: Vision extraction standalone invocability

As a developer,
I want to invoke and test the vision extraction agent independently without starting the analytics module,
So that I can develop and debug the extraction pipeline in isolation.

**Acceptance Criteria:**

**Given** only the extraction-related modules are imported
**When** `POST /extract` is called
**Then** it processes successfully without any import of analytics agent modules (FR42)

**Given** the analytics route files are absent
**When** the extraction agent is invoked directly
**Then** it runs without import errors


---

## Epic 4: End-to-End Data Linkage

**Goal:** The analytics agent is schema-aware of both `shipments` and `extracted_documents` tables, enabling UNION/JOIN queries that return answers spanning historical records and confirmed extracted invoices in a single response.

**FRs:** FR25–FR28
**Depends on:** Epics 2 + 3

---

### Story 4.1: Schema-aware Planner — both tables in analytics prompt context

As a logistics analyst,
I want to ask natural language questions that query my uploaded invoice data using the same chat interface I use for historical shipments,
So that I don't need a separate tool to query documents I've already confirmed.

**Acceptance Criteria:**

**Given** at least one extraction has been confirmed (`confirmed_by_user=1`)
**When** `POST /api/query` is called with a question referencing extracted documents (e.g., "How many invoices have I uploaded?")
**Then** the Planner prompt includes the schema for both `shipments` and `extracted_documents` tables
**And** the generated SQL queries the correct table(s) (FR25)

**Given** the `extracted_documents` table is empty
**When** `POST /api/query` is called with a question about uploaded documents
**Then** the response answers honestly (e.g., "No extracted documents have been confirmed yet") rather than returning a SQL error

---

### Story 4.2: Cross-table query execution and combined response

As a logistics analyst,
I want to ask questions that combine my uploaded invoices with historical shipment data in a single answer,
So that I can compare my specific invoices against the broader dataset.

**Acceptance Criteria:**

**Given** at least one confirmed extraction and the SCMS dataset are present
**When** `POST /api/query` is called with a cross-table question (e.g., "Compare the freight cost of my uploaded invoices to the dataset average for that shipment mode")
**Then** the Executor generates a SQL query using `JOIN` or `UNION` spanning `shipments` and `extracted_documents` (FR27)
**And** the response `answer` presents a combined result drawn from both tables (FR26)
**And** the response arrives within 15 seconds on a cache miss (NFR1)

**Given** the generated cross-table SQL passes the Verifier
**When** it is executed
**Then** `session.execute(text(sql))` runs it without modification — no special handling required for multi-table queries

---

### Story 4.3: SQL transparency for linkage queries in the UI

As a logistics analyst,
I want to see the SQL used for any cross-table query, including both source table names,
So that I can understand exactly how the system is combining my invoice data with historical records.

**Acceptance Criteria:**

**Given** a cross-table query returns a result
**When** the response is rendered in the chat panel
**Then** the collapsible SQL disclosure block shows the full SQL including references to both `shipments` and `extracted_documents` (FR28)
**And** the SQL block remains collapsible and hidden by default (UX-DR6)

**Given** a single-table query returns a result
**When** the response is rendered
**Then** the SQL disclosure shows only the queried table — no change in UI behaviour


---

## Epic 5: Failure Handling & Resilience

**Goal:** Every failure path — malformed LLM output, invalid SQL, API rate limits, model unavailability — returns a structured `ErrorResponse`. No unhandled exceptions. Retry logic and model fallback handled transparently in `ModelClient`.

**FRs:** FR29–FR33
**NFRs:** NFR11
**UX:** UX-DR4

---

### Story 5.1: FastAPI global error handler — ErrorResponse envelope

As a developer,
I want all API errors to return a consistent `ErrorResponse` JSON shape regardless of where the failure occurs,
So that the frontend always receives a structured, parseable error — never a raw Python traceback or FastAPI default `{"detail": ...}`.

**Acceptance Criteria:**

**Given** any unhandled exception occurs in a route handler
**When** FastAPI processes the error
**Then** the response returns the `ErrorResponse` shape: `{"error": true, "error_type": "<type>", "message": "<human message>", "detail": {...}}` (FR29)
**And** the default FastAPI `HTTPException` handler is overridden in `app/main.py` to produce this shape instead of `{"detail": "..."}`

**Given** a validation error occurs (e.g., malformed request body)
**When** FastAPI processes it
**Then** the response returns the `ErrorResponse` shape with `error_type: "validation_error"` — not the default Pydantic error format

**Given** the LLM returns output that cannot be parsed as the expected response schema
**When** the route handler catches the parse failure
**Then** a structured `ErrorResponse` with `error_type: "llm_parse_error"` is returned — the server does not crash (FR29)

---

### Story 5.2: ModelClient retry with corrective instruction

As a developer,
I want `ModelClient` to automatically retry a failed LLM call at least once, appending a corrective instruction to the messages,
So that transient LLM failures and format errors are self-corrected before surfacing an error to the user.

**Acceptance Criteria:**

**Given** `ModelClient.call()` receives a response that fails the caller's parse check
**When** this is the first failure
**Then** `ModelClient` retries the call after 1 second with the original messages plus a corrective instruction appended (e.g., "Your previous response was not valid JSON. Please return only valid JSON.") (FR30)
**And** the log entry records `retry_count=1` (FR37)

**Given** the retry also fails
**When** this is the second consecutive failure
**Then** `ModelClient` retries after 2 seconds, then 4 seconds on a third failure

**Given** all retries are exhausted
**When** the final attempt also fails
**Then** `ModelClient` raises an exception that the route handler catches and converts to an `ErrorResponse` — never surfaces a raw exception to the client

---

### Story 5.3: Rate limit detection and structured response with retry_after

As a logistics analyst,
I want to receive a clear message when the API rate limit is hit, including how long I need to wait before retrying,
So that I know the system is temporarily constrained and when it will recover.

**Acceptance Criteria:**

**Given** the OpenRouter API returns a 429 rate limit response
**When** `ModelClient` receives it
**Then** it returns an `ErrorResponse` with `error_type: "rate_limit"`, a human-readable `message`, and a `retry_after` field (integer seconds) (FR31)
**And** the response is returned within 5 seconds of the connection timeout (NFR11)

**Given** the OpenRouter API is completely unreachable (connection timeout)
**When** `ModelClient` detects the timeout
**Then** it returns an `ErrorResponse` with `error_type: "model_unavailable"` within 5 seconds of the timeout (NFR11)

---

### Story 5.4: Invalid or unsafe SQL — structured error with failed query

As a logistics analyst,
I want to receive a clear error message when the system generates SQL that is invalid or unsafe, including the problematic query,
So that I understand what went wrong and can rephrase my question.

**Acceptance Criteria:**

**Given** the Verifier rejects generated SQL containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, or `ALTER` targeting `shipments`
**When** the rejection is returned to the route handler
**Then** the response is an `ErrorResponse` with `error_type: "unsafe_sql"`, a human-readable message, and `detail.sql` containing the rejected query (FR32)

**Given** the LLM generates syntactically invalid SQL that fails execution
**When** SQLAlchemy raises an exception during `session.execute()`
**Then** the route handler catches it and returns an `ErrorResponse` with `error_type: "sql_execution_error"` and `detail.sql` containing the failed query (FR32)

---

### Story 5.5: Automatic fallback model on primary model failure

As a logistics analyst,
I want the system to automatically switch to a backup model when the primary model is unavailable,
So that temporary model outages don't fully block my queries.

**Acceptance Criteria:**

**Given** the primary analytics model (Llama 3.3 70B) fails after all retries are exhausted
**When** `ModelClient` detects the final failure
**Then** it automatically retries the same call using the fallback model (DeepSeek R1) (FR33)
**And** the log entry records `model_name: "deepseek-r1"` and `fallback: true`

**Given** the primary vision model (Qwen3 VL 235B) fails after all retries
**When** `ModelClient` detects the final failure
**Then** it automatically retries using the fallback vision model (Nemotron Nano VL) (FR33)

**Given** both primary and fallback models fail
**When** all attempts are exhausted
**Then** an `ErrorResponse` with `error_type: "model_unavailable"` is returned — no crash

---

### Story 5.6: Error toast UI with countdown timer

As a logistics analyst,
I want to see a clear error toast when something goes wrong, with a countdown timer when I need to wait before retrying,
So that I'm informed of failures without being left staring at a broken UI.

**Acceptance Criteria:**

**Given** any API call returns an `ErrorResponse`
**When** the frontend receives it
**Then** an error toast is displayed with the `message` text from the response (UX-DR4)

**Given** the `ErrorResponse` includes a `retry_after` field (rate limit scenario)
**When** the toast is displayed
**Then** it shows a countdown timer ticking down from `retry_after` seconds until the user can retry (FR31, UX-DR4)

**Given** the countdown reaches zero
**When** the timer expires
**Then** the toast updates to indicate the user can retry — the input is re-enabled

**Given** an error occurs that has no `retry_after`
**When** the toast is displayed
**Then** no countdown timer is shown — just the error message with a dismiss button


---

## Epic 6: Deployment & Demo Readiness

**Goal:** The system is publicly accessible, cold-startable from scratch, and has everything an evaluator needs: Vercel + Render deployment, Docker Compose for local dev, a README with architecture overview and demo script, and synthetic freight invoices ready to upload.

**NFRs:** NFR6, NFR9, NFR12
**Depends on:** Epics 1–5

---

### Story 6.1: Docker Compose — single command local startup

As a developer,
I want a `docker-compose.yml` at the repo root that wires the backend and frontend together,
So that the full system can be started locally with a single command from a cold clone.

**Acceptance Criteria:**

**Given** the developer clones the repo, copies `.env.example` to `.env`, and fills in `OPENROUTER_API_KEY`
**When** they run `docker-compose up`
**Then** both the backend (port 8000) and frontend (port 3000) start without errors
**And** the frontend can successfully call backend API routes (CORS wildcard `*` configured)
**And** `GET http://localhost:8000/api/health` returns `{"status": "ok"}`

**Given** the developer runs `docker-compose up` on a machine that has never built these images
**When** the build completes
**Then** all dependencies are installed from `pyproject.toml` / `pnpm-lock.yaml` without any manual steps

---

### Story 6.2: Backend deployment to Render

As a developer,
I want the FastAPI backend deployed and publicly accessible on Render via Docker,
So that evaluators can hit the live API without local setup.

**Acceptance Criteria:**

**Given** the backend Docker image is built and pushed to Render
**When** Render completes the deploy
**Then** `GET https://<render-url>/api/health` returns `{"status": "ok"}` within 60 seconds of cold start (NFR12)
**And** all communication is over HTTPS (NFR9)
**And** `OPENROUTER_API_KEY` is configured as a Render environment variable — not committed to the repo (NFR10)

**Given** the backend deploys to Render
**When** `GET https://<render-url>/docs` is opened
**Then** the Swagger UI is accessible without authentication (FR36)

---

### Story 6.3: Frontend deployment to Vercel

As a developer,
I want the Next.js frontend deployed and publicly accessible on Vercel,
So that evaluators can open the app at a URL with no local setup.

**Acceptance Criteria:**

**Given** the frontend is deployed to Vercel
**When** the evaluator opens the Vercel URL in a browser
**Then** the SPA loads and renders within 5 seconds on a cold start (NFR6)
**And** all API calls go to the Render backend URL over HTTPS (NFR9)
**And** the backend URL is configured as a Vercel environment variable (`NEXT_PUBLIC_API_URL`) — not hardcoded in source

**Given** the evaluator uses the chat panel on the live deployment
**When** they submit a question
**Then** the response is returned correctly from the Render backend — no CORS errors

---

### Story 6.4: Synthetic freight invoice demo files

As an evaluator,
I want 5–6 synthetic freight invoice files (mix of PDF and image formats) ready to upload,
So that I can demonstrate the Vision Extraction agent without needing to source my own documents.

**Acceptance Criteria:**

**Given** the demo invoices are included in the repo under `backend/data/demo_invoices/`
**When** each file is uploaded via the upload panel
**Then** the extraction returns plausible freight fields (shipment mode, origin/destination country, weight, cost, dates)
**And** at least one invoice has a LOW or NOT_FOUND confidence field to demonstrate the confidence badge behaviour (FR14)
**And** at least one invoice uses a shipment mode and country present in the SCMS dataset to enable a meaningful linkage query

**Given** the invoices are inspected
**When** the formats are checked
**Then** the set includes at least 2 PDFs and at least 1 image file (PNG or JPG) to exercise both upload paths (FR9, FR10)

---

### Story 6.5: README with architecture overview, setup guide, and demo script

As an evaluator,
I want a README that explains the system architecture, how to run it locally, and a step-by-step demo script,
So that I can evaluate the system without needing to decipher the codebase first.

**Acceptance Criteria:**

**Given** the evaluator opens the repo
**When** they read the README
**Then** it contains: a 1-paragraph project summary, an architecture diagram (Mermaid or ASCII) showing Planner → Executor → Verifier → SQLite, the tech stack table, and a step-by-step demo script covering all 5 evaluation journeys

**Given** the evaluator follows the local setup section
**When** they run the documented commands
**Then** the system starts successfully — the README instructions are accurate and tested

**Given** the evaluator reads the demo script
**When** they follow it sequentially
**Then** it covers: (1) analytics query on SCMS data, (2) document upload and extraction review, (3) confirm extraction and query it, (4) cross-table linkage query, (5) deliberate failure path demonstration

