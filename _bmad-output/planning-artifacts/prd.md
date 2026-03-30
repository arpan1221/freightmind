---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
inputDocuments: ['_bmad-output/planning-artifacts/product-brief.md', 'BMAD_BRAIN_DUMP.md', 'TECH_DECISIONS.md', 'DATASET_SCHEMA.md', 'DAW_AI_SSE_Part 1_Assignment.pdf']
workflowType: 'prd'
classification:
  projectType: 'web_app_fullstack'
  domain: 'logistics_supply_chain'
  complexity: 'medium_high'
  projectContext: 'greenfield'
  complexityDrivers: ['llm_orchestration', 'multimodal_inputs', 'shared_data_store_linkage', 'rate_limit_constraints', 'ephemeral_storage']
  prdFocus: ['backend_requirements', 'failure_modes', 'confidence_thresholds', 'null_handling_business_rules']
  partyModeInsights: 'accepted'
briefCount: 1
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
---

# Product Requirements Document — FreightMind

**Author:** Arpan
**Date:** 2026-03-30

---

## Executive Summary

FreightMind is a proof-of-concept agentic AI platform built as a GoComet AI Solutions Engineer take-home submission (Part 1). It demonstrates two AI capabilities — Agentic Analytics and Vision Document Extraction — operating over a shared SQLite data store, proving end-to-end linkage between structured historical records and freshly extracted invoice data.

The system is pre-loaded with 10,324 shipment records from the USAID Supply Chain Management System (SCMS) — real health commodity logistics data covering freight costs, shipment modes (Air/Ocean/Truck/Air Charter), delivery timelines, vendor performance, and weight across 15+ countries. The freight mechanics are domain-agnostic and directly applicable to commercial logistics contexts. Business users interact via a Next.js frontend deployed on Vercel; all AI orchestration runs on a FastAPI backend deployed on Render. No local setup is required for evaluation.

The differentiator is the linkage: either agent alone is a demo. Together — where a PDF freight invoice becomes queryable data that the analytics agent can JOIN against historical records — the system demonstrates something real: an AI pipeline where unstructured documents become first-class analytical assets without manual data entry. This is implemented through a shared SQLite schema (`shipments` + `extracted_documents` + `extracted_line_items`), a schema-aware analytics prompt that understands both tables, and a user-facing review-before-commit extraction flow that keeps humans in control of data quality. The architecture enforces clear separation: Planner routes intent, Executors specialise by task (SQL generation vs. vision extraction), Verifier validates output before it touches the database. Each agent is independently runnable.

The system's design thesis: transparency is the trust mechanism. Every analytics response shows the SQL query used. Every extracted field shows a confidence score. Every failure — malformed LLM output, low-confidence extraction, unanswerable question, rate limit — returns a structured, honest response rather than a silent error or hallucinated answer. The sentinel values present in the SCMS dataset (`"Freight Included in Commodity Cost"`, `"Weight Captured Separately"`) are handled via explicit business rules — documented, not silently coerced to zero or NULL.

### Project Classification

| Attribute | Value |
|-----------|-------|
| Project Type | Full-stack web application (Next.js SPA + FastAPI REST backend) |
| Domain | Logistics / Supply Chain (USAID SCMS health commodity freight data) |
| Complexity | Medium-high — LLM orchestration, multimodal inputs, shared data store linkage, 50 req/day rate limit constraint |
| Project Context | Greenfield |
| Evaluation Rubric | Working E2E (30%) · Failure Handling (25%) · Architecture (20%) · Transparency (15%) · Code Quality (10%) |

---

## Success Criteria

### User Success

The primary "user" for this POC is the GoComet evaluator running the demo from a clean environment.

- **Zero setup friction:** Evaluator clicks Vercel URL, system loads with pre-populated dataset, no local commands required
- **Demo completes without errors:** Analytics query → extraction flow → linkage query completes end-to-end in the 1–2 minute demo script
- **Transparency is legible:** A non-engineer can read the SQL query, understand the confidence scores, and see why a failure occurred — without reading the code
- **Honest failures:** When given a bad document or an unanswerable question, the system explains what happened rather than returning empty results or crashing

### Business Success

For this context, business success = passing Part 1 and receiving a Part 2 invitation.

| Outcome | Target |
|---------|--------|
| Evaluator score: Working E2E system | All 3 behaviours (A, B, C) pass from clean environment |
| Evaluator score: Failure handling | 4 failure modes explicitly demonstrated and documented |
| Evaluator score: Architecture | Planner/Executor/Verifier separation visible in code structure |
| Evaluator score: Transparency | Every response includes query logic and/or confidence data |
| Evaluator score: Code quality | README enables cold-start run; zero unexplained TODOs in critical paths |
| Part 2 invitation | Received within evaluation window |

### Technical Success

| Requirement | Acceptance Condition |
|-------------|---------------------|
| Analytics agent | NL question → SQL → result table + chart in <10s (cached) |
| SQL transparency | Raw SQL included in every `/api/analytics/query` response |
| Vision extraction | 14 fields extracted with per-field confidence score (HIGH/MEDIUM/LOW) |
| Null handling | `freight_cost_usd` and `weight_kg` sentinel values → explicit NULL with documented business rule |
| Linkage query | UNION/JOIN across `shipments` + `extracted_documents` returns correct results |
| Failure handling | 4 paths implemented: malformed LLM output, low-confidence field, unanswerable question, rate limit |
| Fallback models | Primary → fallback switchover works for both text (Llama → DeepSeek) and vision (Qwen VL → Nemotron) |
| Independent modules | Analytics agent and Vision agent each runnable standalone via documented command |
| Configurable prompts | All prompts in `prompts/` directory — zero hardcoded prompt strings in business logic |
| Schema documented | `/api/schema` endpoint + README both expose full database schema |
| Cold-start deploy | Render startup script loads CSV + initialises schema automatically |

### Measurable Outcomes

- **0** unhandled exceptions surfaced to the user in normal demo flow
- **4** failure modes explicitly tested and passing
- **14** fields extracted with confidence from a clean synthetic invoice
- **3** tables in shared SQLite schema queryable by the analytics agent
- **1** cross-table linkage query demonstrating A→B connection in demo script
- **2** deployed URLs (Vercel + Render) accessible without credentials

---

## Product Scope

Three development phases map to assignment milestones. Full capability detail and time allocation are in the Project Scoping section.

| Phase | Timeline | Scope |
|-------|----------|-------|
| **MVP** — Part 1 | 24 hours | Analytics agent (NL→SQL+chart), Vision extraction (14 fields + confidence), End-to-end linkage, 4 failure modes, full deployment |
| **Growth** — Part 2 | 3–4 hours post-evaluation | Multi-role verification workflow (SU submits → CG approves/rejects), audit trail fields |
| **Vision** — Post-assignment | Ongoing | Streaming (SSE), authentication, production database (Postgres), bulk upload, webhooks |

**Explicitly deferred from Part 1:** Streaming, authentication/roles, non-English invoice support, mobile-responsive polish, automated test suite.

---

## User Journeys

### Journey 1: The Evaluator — Analytics Flow (Primary Success Path)

**Persona:** Priya, Senior Engineer at GoComet, evaluating 6 candidates' Part 1 submissions in a single afternoon. She has 10 minutes per submission. She's seen a lot of demos that work locally but fail on her machine.

**Opening Scene:** Priya opens the submission README. She's looking for one thing first: a live URL. She finds it. She clicks the Vercel link. FreightMind loads in 3 seconds with a chat interface and a dataset summary card showing "10,324 shipment records loaded." No setup, no terminal, no `pip install`. She exhales.

**Rising Action:** She types the first sample question from the README: *"What is the total freight cost by shipment mode?"* The system responds in 4 seconds: a text answer, a bar chart with four bars (Air, Ocean, Truck, Air Charter), a result table, and — crucially — the SQL query that produced it, displayed in a collapsible code block. She expands it. The SQL is clean, readable, and correct.

**Climax:** She tries a follow-up not in the script: *"Filter that to just Nigeria."* The system maintains context, issues a new query with a `WHERE country = 'Nigeria'` clause appended, and returns an updated chart. It didn't ask her to rephrase. It didn't forget the previous question. She writes "+1 context handling" in her notes.

**Resolution:** She asks an unanswerable question: *"What is the profit margin by vendor?"* The system responds: *"Profit margin data is not available in this dataset. The dataset contains freight cost and line item value — these cover cost, not margin. Would you like to see freight cost per unit by vendor instead?"* It didn't hallucinate. It told her what it could do instead.

**Capabilities revealed:** Chat interface, SQL transparency panel, chart rendering, follow-up context handling, out-of-scope graceful refusal with alternatives.

---

### Journey 2: The Evaluator — Extraction + Linkage Flow (Primary Success Path)

**Persona:** Same Priya, now testing Part B and C of the rubric.

**Opening Scene:** She switches to the "Upload Document" tab. She drags in `sample_invoice_clean.pdf` — one of the synthetic invoices included in the repo. A loading spinner appears for 6 seconds, then a review panel populates with 14 extracted fields.

**Rising Action:** Most fields show a green HIGH confidence badge. But `payment_terms` shows MEDIUM in amber, and `total_insurance_usd` shows LOW in red with a note: *"Value unclear in document — please verify before storing."* She appreciates that it didn't just guess. She edits `total_insurance_usd` to the correct value from the invoice, then clicks Confirm.

**Climax:** She switches back to the chat and types: *"Compare the freight cost from my uploaded invoice to the dataset average for Air shipments."* The system runs a UNION query across `shipments` and `extracted_documents`, returns a two-row table — dataset average vs. extracted invoice value — with the SQL shown. The linkage is live.

**Resolution:** She marks the submission for Part 2 follow-up.

**Capabilities revealed:** File upload, vision extraction with per-field confidence, editable review panel, confirm-to-store flow, cross-table linkage query, UNION SQL transparency.

---

### Journey 3: The Logistics Analyst — Daily Use Persona (Demonstrated User)

**Persona:** Daniel, Operations Analyst at a freight forwarder. He receives 20–30 freight invoices a week as PDFs in email. His job: reconcile them against the shipment records in the company database. Currently this takes 2–3 hours per week of manual entry.

**Opening Scene:** Daniel receives a freight invoice from a carrier in Lagos. He opens FreightMind, drags the PDF in. The system extracts all 14 fields in under 10 seconds. He reviews, corrects one field where the carrier printed an ambiguous weight format, confirms, and it's in the database.

**Rising Action:** A week later, his manager asks: *"Are our Air shipments to Nigeria costing more than average since the new carrier contract started?"* In the old world, Daniel would spend an hour writing SQL and Excel formulas. Now he types the question. The system queries both historical records and his extracted invoices, returns a chart showing the trend.

**Resolution:** Daniel has turned a 3-hour weekly process into 20 minutes and can now answer analytical questions that previously required an analyst. The system didn't replace his judgment — it removed the friction that blocked it.

**Capabilities revealed:** End-to-end workflow continuity, human-in-loop extraction review, analytical queries over mixed data sources.

---

### Journey 4: The Evaluator — Failure Handling Path (Edge Case)

**Persona:** Priya, now specifically stress-testing the 25% failure handling rubric.

**Scene 1 — Bad document:** She uploads `sample_invoice_noisy.pdf` — a low-quality, slightly rotated scan. Five fields show LOW confidence. Two show `NOT FOUND`. The UI flags them in red. She can confirm high-confidence fields and leave low ones blank. The system didn't crash. It told her exactly what it couldn't do.

**Scene 2 — Rate limit:** Rapid requests trigger a rate limit. The system returns a structured error: `{"error": "rate_limit", "message": "OpenRouter rate limit reached. Please wait 60 seconds.", "retry_after": 60}`. The frontend shows a countdown timer. No crash, no white screen.

**Scene 3 — Malformed LLM output:** She checks the logs. The system caught a JSON parse error, retried once with an explicit JSON instruction appended, succeeded, and logged the original failure. The user saw nothing.

**Resolution:** She gives full marks on failure handling.

**Capabilities revealed:** Per-field `NOT_FOUND` state, LOW confidence UI treatment, rate limit structured response + frontend countdown, LLM output retry logic, structured error logging.

---

### Journey 5: The Operator — Cold-Start Deploy (Setup Path)

**Persona:** Priya's colleague, running a local evaluation before the committee review.

**Opening Scene:** He clones the repo. Follows three steps in the README: `cp .env.example .env`, add OpenRouter API key, `docker-compose up`. The backend starts, the startup script fires: CSV loads, SQLite schema initialises, health check passes at `/api/health`. The frontend connects. The system is live in under 5 minutes.

**Resolution:** He didn't need to ask anyone anything. The README had everything. The schema was documented. Sample invoices were in the repo. He ran the demo script exactly as written.

**Capabilities revealed:** Environment variable configuration, Docker-based startup, automated DB initialisation script, `/api/health` endpoint, self-contained repo with sample data.

---

### Journey Requirements Summary

| Capability | Revealed By |
|------------|-------------|
| Chat interface with context retention | Journey 1 |
| SQL transparency panel (collapsible) | Journeys 1, 2 |
| Chart rendering (bar/line) | Journey 1 |
| Out-of-scope graceful refusal with alternatives | Journey 1 |
| File upload (PDF/image) | Journeys 2, 4 |
| Per-field confidence display (HIGH/MEDIUM/LOW/NOT_FOUND) | Journeys 2, 4 |
| Editable extraction review panel | Journeys 2, 3 |
| Confirm-to-store flow | Journeys 2, 3 |
| Cross-table UNION linkage query | Journeys 2, 3 |
| Rate limit structured response + frontend countdown | Journey 4 |
| LLM output retry logic with logging | Journey 4 |
| Docker cold-start with automated DB init | Journey 5 |
| `/api/health` endpoint | Journey 5 |
| Self-contained sample data in repo | Journey 5 |

---

## Domain-Specific Requirements

### Data Integrity Rules (Freight/Supply Chain)

Freight data has well-understood business semantics that the system must respect:

| Rule | Requirement |
|------|-------------|
| Sentinel freight costs | `"Freight Included in Commodity Cost"` and `"Invoiced Separately"` → stored as NULL, excluded from cost averages; displayed to user as "not separately reported" in query explanations |
| Sentinel weights | `"Weight Captured Separately"` → stored as NULL; analytics agent must note exclusions when computing weight-based metrics |
| NULL ≠ zero | Averaging freight costs must use `WHERE freight_cost_usd IS NOT NULL`; treating NULL as zero would distort every cost metric |
| Delivery delay calculation | `delivered_to_client_date - scheduled_delivery_date`; rows where either date is NULL must be excluded from delay analytics, not treated as on-time |
| Shipment mode vocabulary | Accepted values: `Air`, `Ocean`, `Truck`, `Air Charter` — extraction agent must normalise synonyms (e.g., "Airfreight" → "Air", "Sea" → "Ocean") before storage |
| Country name normalisation | Extracted `destination_country` must match dataset country names exactly for linkage JOINs to work (e.g., "Congo (DRC)" not "Democratic Republic of Congo") |

### Freight Document Field Standards

The 14 extracted fields follow standard freight invoice conventions. The system must handle:

- **Multi-currency**: Invoices may show amounts in local currency; extraction agent should note the currency and store USD equivalent if shown, or flag for user review
- **Multi-page invoices**: Line items may span pages; extraction must aggregate across all pages before computing totals
- **Date formats**: Invoice dates appear in multiple formats (DD/MM/YYYY, MM-DD-YYYY, written month); extraction must normalise to ISO 8601 before storage
- **Weight units**: Invoices may use kg, lbs, or MT; extraction must normalise to kg before storing `total_weight_kg`

### Technical Constraints (AI-Specific)

| Constraint | Requirement |
|------------|-------------|
| Rate limit: 50 req/day | File-based response cache mandatory in development; `BYPASS_CACHE=true` env var for fresh calls during demo |
| Rate limit: 20 req/min | Retry with exponential backoff (1s, 2s, 4s) before surfacing rate limit error to user |
| Ephemeral Render storage | DB initialisation script runs on every startup; extracted documents do not persist across deploys — documented as known limitation |
| Vision model context window | Qwen3 VL 235B supports large context; PyMuPDF converts each PDF page to image separately to avoid multi-page context limits |
| Prompt configurability | Zero hardcoded prompt strings in business logic; all prompts in `backend/prompts/` as Python string constants or `.txt` files |

### Data Integrity Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Country name mismatch breaks linkage | Extraction prompt includes list of exact country names from dataset; LLM normalises to closest match |
| Shipment mode synonym breaks JOIN | Extraction prompt provides accepted vocabulary; post-extraction validation rejects invalid modes and flags for user correction |
| NULL exclusions skew analytics | Analytics agent system prompt explicitly documents NULL handling rules; every response that excludes NULLs notes the exclusion count |
| Multi-currency extraction confusion | Extraction prompt instructs model to extract the USD value if shown; otherwise extract as-is and flag currency for user review |

---

## Innovation & Novel Patterns

### Composable Dual-Agent Architecture with Shared Queryable Store

The core innovation is not either agent individually — it is that the extraction agent's output becomes a first-class data source for the analytics agent. Most document AI tools produce exports or dashboards. FreightMind produces *queryable tables*. The analytics agent is schema-aware of both `shipments` (historical) and `extracted_documents` (runtime), enabling UNION and JOIN queries that span both. This collapses what would normally be two separate systems — a document processing pipeline and an analytics layer — into a single coherent interface.

### Transparency as Trust Infrastructure

The design assumption is that an LLM-powered system can only be trusted if its reasoning is visible. Every analytics response includes the raw SQL. Every extracted field includes a confidence score. Every NULL exclusion is noted in the response text. This is not logging — it is the UX. For AI tools to earn trust in professional contexts, uncertainty must be surfaced to the person making decisions, not absorbed by the system.

### Failure-First Architecture

The system is designed around its failure modes before its success modes. The four failure paths (malformed output, low-confidence extraction, unanswerable question, rate limit) are first-class features with structured responses, not edge cases with try/except blocks. The Verifier layer exists specifically to intercept failures before they reach the user, inverting the typical build-happy-path-then-handle-errors approach.

### Innovation Validation

| Innovation | Validation Method |
|------------|------------------|
| Dual-agent linkage | Demo script includes explicit cross-table UNION query returning correct results |
| Transparency as trust | Evaluator can read SQL and confidence scores without reading code — tested by Journey 1 and 2 |
| Failure-first architecture | 4 failure modes explicitly triggered in demo; all return structured responses, zero crashes |

### Architecture Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Linkage JOINs fail due to schema mismatch | Extraction normalises `shipment_mode` and `country` to dataset vocabulary before storage |
| Transparency adds response latency | SQL and confidence data computed during generation, not post-processed — no additional LLM call |
| Failure handling adds code complexity | Verifier layer isolates failure logic; executor code stays clean |

---

## Full-Stack Web Application Requirements

### Architecture Overview

FreightMind is a **Single Page Application** (SPA) frontend communicating with a **REST API** backend. The frontend is a thin presentation layer — its job is to render chat, file upload, tables, and charts. All AI orchestration, data access, and business logic lives in the backend.

Out of scope by design: SEO, mobile/responsive beyond basic usability, accessibility beyond semantic HTML, CLI interface.

---

### Frontend Requirements (Next.js SPA)

| Concern | Decision |
|---------|----------|
| SPA vs MPA | SPA — single layout with tab navigation between Analytics and Document views |
| Browser support | Modern Chrome/Firefox/Safari — no legacy support needed for a demo |
| Real-time | No streaming — synchronous request/response with loading states |
| Accessibility | Semantic HTML, colour contrast for confidence badges (HIGH=green, MEDIUM=amber, LOW=red) |
| State management | React useState/useContext — no Redux needed at this scale |
| Chart library | Recharts — React-native, handles bar/line/pie with minimal config |
| File upload | Native `<input type="file">` with drag-and-drop; accepts `.pdf`, `.png`, `.jpg`, `.jpeg` |

**UI Components Required:**

1. **Chat panel** — message thread, input box, loading spinner, SQL disclosure block (collapsible), result table, chart area, follow-up suggestions
2. **Upload panel** — drop zone, file preview, extraction review table (editable fields, confidence badges), confirm/cancel buttons
3. **Dataset status card** — shows row count, table names, last loaded timestamp
4. **Error toast** — structured error display for rate limits, parse failures, network errors

---

### Backend API Requirements (FastAPI)

#### Endpoint Specifications

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/analytics/query` | NL question → SQL → result + chart config |
| `POST` | `/api/documents/extract` | File upload → vision extraction → confidence scores |
| `POST` | `/api/documents/confirm` | User-reviewed extraction → store to SQLite |
| `GET` | `/api/documents/list` | List all confirmed extracted documents |
| `GET` | `/api/schema` | Full DB schema + sample values (transparency endpoint) |
| `GET` | `/api/health` | Service health check (DB connected, model reachable) |

#### Request/Response Contracts

**`POST /api/analytics/query`**
```json
// Request
{ "question": "string", "context": { "previous_sql": "string|null", "filters": {} } }

// Response
{
  "answer": "string",
  "sql": "string",
  "data": [{}],
  "row_count": 0,
  "null_exclusions": 0,
  "chart_config": { "type": "bar|line|pie", "x_key": "string", "y_key": "string" },
  "suggestions": ["string"],
  "error": null
}
```

**`POST /api/documents/extract`**
```json
// Request: multipart/form-data with file

// Response
{
  "extraction_id": "string",
  "fields": {
    "invoice_number": { "value": "string|null", "confidence": "HIGH|MEDIUM|LOW|NOT_FOUND" },
    "destination_country": { "value": "string|null", "confidence": "HIGH|MEDIUM|LOW|NOT_FOUND" }
  },
  "line_items": [{ "description": "string", "quantity": 0, "unit_price": 0.0, "total_price": 0.0, "confidence": "HIGH|MEDIUM|LOW" }],
  "error": null
}
```

**`POST /api/documents/confirm`**
```json
// Request
{ "extraction_id": "string", "corrections": { "field_name": "corrected_value" } }

// Response
{ "stored": true, "document_id": 0 }
```

#### Authentication

None — public demo POC. No auth required for Part 1. Part 2 adds role-based access.

#### Data Formats

- All requests/responses: `application/json` (except file upload: `multipart/form-data`)
- Dates: ISO 8601 (`YYYY-MM-DD`) in all responses
- Monetary values: floats in USD
- Confidence: enum string `HIGH | MEDIUM | LOW | NOT_FOUND`
- Error shape: `{ "error": "error_type", "message": "human-readable", "retry_after": null|int }`

#### Rate Limiting (OpenRouter)

- 50 requests/day, 20 req/min on free tier
- Backend enforces exponential backoff: 1s → 2s → 4s, max 3 retries
- After 3 failures: returns structured `rate_limit` error to client
- Frontend shows countdown timer when `retry_after` is present

#### API Versioning

No versioning for this POC — single version at root paths.

#### Auto-Generated Documentation

FastAPI generates OpenAPI docs at `/docs` (Swagger UI) and `/redoc` — serves as the transparency layer for evaluators.

---

### Data Schemas

See `DATASET_SCHEMA.md` for full SQLite DDL. Summary:

| Table | Purpose | Row Source |
|-------|---------|-----------|
| `shipments` | 10,324 pre-loaded SCMS records | CSV loaded at startup |
| `extracted_documents` | User-confirmed invoice extractions | `POST /api/documents/confirm` |
| `extracted_line_items` | Line items from extracted invoices | Same confirm flow |

---

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Analytics query (cached) | < 2s | Cache hit returns stored response |
| Analytics query (live LLM) | < 15s | Llama 3.3 70B inference time |
| Document extraction (cached) | < 3s | Cache hit |
| Document extraction (live LLM) | < 30s | Qwen VL 235B, large model |
| Page load (Vercel cold) | < 5s | Static SPA, no SSR needed |
| DB query (SQLite local) | < 100ms | Indexes on key columns |

---

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Evaluation MVP — the minimum that satisfies all three required behaviours (A, B, C) from the assignment rubric, deployed and publicly accessible, with failure handling that actively demonstrates engineering maturity. The scope is fixed by the assignment; every scoping decision is a **build priority decision** given the 24-hour constraint, not a feature discovery decision.

**Resource requirements:** Solo developer, 24 hours, around existing day job commitments.

| Area | Time Allocation |
|------|----------------|
| Backend core (planner/executor/verifier + SQLite + analytics agent) | ~8 hours |
| Vision extraction agent + confidence scoring | ~4 hours |
| Frontend (chat + upload + review panels) | ~5 hours |
| Deployment (Vercel + Render + env config) | ~2 hours |
| Synthetic invoice generation | ~2 hours |
| README + demo script + testing | ~3 hours |

### MVP Feature Set (Phase 1) — Part 1, 24 Hours

**Core User Journeys Supported:** Journeys 1, 2, 4, 5 (evaluator analytics, extraction+linkage, failure handling, cold-start)

| Capability | Without This... |
|------------|----------------|
| NL → SQL → result + chart | Assignment behaviour A fails |
| SQL shown in every response | Transparency rubric fails |
| Follow-up context handling | Assignment behaviour A fails |
| PDF/image → extraction → confidence | Assignment behaviour B fails |
| Per-field NOT_FOUND/LOW flagging | Failure handling rubric fails |
| Review-before-confirm flow | Assignment behaviour B fails |
| Cross-table UNION linkage query | Assignment behaviour C fails (hard failure) |
| 4 failure modes with structured responses | Failure handling rubric fails |
| Prompts in `prompts/` directory | Architecture rubric fails |
| Independent module runability | Architecture rubric fails |
| Cold-start DB initialisation | Code quality rubric fails |
| README with demo script | Code quality rubric fails |

### Post-MVP Features

**Phase 2 — Part 2 (3–4 hours after Part 1 evaluation):**
- SU → CG verification workflow
- `verification_status` enum on `extracted_documents`
- Role-differentiated UI (submit vs. review views)
- Audit trail fields (`submitted_by`, `reviewed_by`, `reviewed_at`)

**Phase 3 — Production extension (post-assignment):**
- Authentication and multi-tenant support
- Postgres replacing SQLite
- Real-time streaming (SSE)
- Bulk document upload + batch extraction
- Webhook notifications

### Build Risk Mitigations

**Technical risks:**

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Vision model quality insufficient for extraction | Medium | Test early with clean synthetic invoice; fallback to Nemotron Nano VL |
| LLM SQL generation fails on complex queries | Low | Schema-aware prompts with sample values; fallback to DeepSeek R1 |
| Render cold start > 30s | Medium | Include `/api/health` warmup in README demo script; document as known behaviour |
| Linkage JOIN breaks due to country/mode mismatch | Medium | Extraction prompt enforces dataset vocabulary; validation step pre-storage |

**Resource risks (time crunch):**

| Scenario | Contingency |
|----------|------------|
| Backend takes longer than 12h | Cut chart types to bar-only; simplify follow-up context to last-SQL-only |
| Vision model rate limits exhausted | Switch to cached demo mode; commit cache files to repo |
| Render deployment fails | Fall back to local + ngrok for demo; document in README |
| Frontend takes longer than planned | Ship minimal Tailwind UI; evaluator is an engineer, not a designer |

---

## Functional Requirements

### Natural Language Analytics

- **FR1:** User can submit a natural language question about shipment data and receive a data-backed text answer
- **FR2:** User can view the exact SQL query used to produce any analytics response
- **FR3:** User can view analytics query results as a structured data table with column headers and row counts
- **FR4:** User can view at least one chart visualisation (bar, line, or pie) for quantitative analytics results
- **FR5:** User can submit a follow-up question that refines a previous query result by filter, grouping, or time window
- **FR6:** System can detect when a question references data not present in the dataset and returns a clear explanation of what data is available
- **FR7:** System surfaces the count of records excluded from a query due to NULL values in the response text
- **FR8:** User can view suggested follow-up questions after receiving an analytics response

### Document Upload & Vision Extraction

- **FR9:** User can upload a PDF document for structured field extraction
- **FR10:** User can upload an image file (PNG, JPG, JPEG) for structured field extraction
- **FR11:** System extracts 14 defined structured fields from an uploaded freight document using a vision-capable model
- **FR12:** System extracts line items (description, quantity, unit price, total price) from an uploaded document
- **FR13:** System assigns a confidence level (HIGH, MEDIUM, LOW, or NOT_FOUND) to each extracted field
- **FR14:** System visually distinguishes LOW confidence and NOT_FOUND fields from HIGH/MEDIUM confidence fields in the extraction review
- **FR15:** System normalises extracted shipment mode values to accepted vocabulary (Air, Ocean, Truck, Air Charter) before presenting for review
- **FR16:** System normalises extracted country names to dataset vocabulary before presenting for review
- **FR17:** System normalises extracted dates to ISO 8601 format (YYYY-MM-DD) before presenting for review
- **FR18:** System normalises extracted weight values to kilograms before presenting for review

### Extraction Review & Confirmation

- **FR19:** User can review all extracted fields before any data is stored
- **FR20:** User can edit any extracted field value in the review panel before confirming
- **FR21:** User can confirm a reviewed extraction to persist it to the shared data store
- **FR22:** User can cancel an extraction without storing any data
- **FR23:** System stores confirmed extractions in a queryable format accessible to the analytics layer
- **FR24:** User can view a list of all previously confirmed extracted documents

### End-to-End Data Linkage

- **FR25:** User can ask natural language questions that query extracted document data using the same analytics interface as historical data
- **FR26:** System can return answers that combine data from both historical shipment records and confirmed extracted documents in a single response
- **FR27:** System can execute cross-table queries spanning `shipments` and `extracted_documents` tables
- **FR28:** User can view the SQL for any linkage query, showing both source tables referenced

### Failure Handling & Recovery

- **FR29:** System returns a structured error response when the LLM produces malformed or unparseable output, without crashing
- **FR30:** System retries a failed LLM call at least once with a corrective instruction appended before surfacing an error to the user
- **FR31:** System returns a structured error response when an API rate limit is reached, including the duration before the next retry is possible
- **FR32:** System returns a structured error response when a user question produces invalid or unsafe SQL, including the failed query for transparency
- **FR33:** System automatically switches to a fallback model when the primary model is unavailable or fails after retries

### System Transparency

- **FR34:** System exposes the complete database schema, table row counts, and sample column values via a dedicated read-only endpoint
- **FR35:** System provides a health check endpoint reporting database connection status and model reachability
- **FR36:** System auto-generates and exposes interactive API documentation accessible without authentication
- **FR37:** System logs each LLM API call with model name, cache hit/miss status, and retry count

### Data Initialisation & Configuration

- **FR38:** System automatically loads the SCMS CSV dataset into the database on startup when the shipments table is empty
- **FR39:** System automatically creates all required database tables and indexes on startup if they do not exist
- **FR40:** All LLM prompt templates are stored in dedicated configuration files separate from business logic code
- **FR41:** The analytics agent module can be invoked and tested independently without the vision extraction module
- **FR42:** The vision extraction module can be invoked and tested independently without the analytics agent module

### Response Caching

- **FR43:** System caches LLM API responses keyed by a hash of the request payload to avoid redundant API calls during development
- **FR44:** System provides an environment-variable-controlled option to bypass the response cache for fresh API calls

---

## Non-Functional Requirements

### Performance

- **NFR1:** Analytics query responses (cache miss) must complete within 15 seconds under normal network conditions
- **NFR2:** Document extraction responses (cache miss) must complete within 30 seconds for single-page PDFs
- **NFR3:** All cached responses (analytics or extraction) must be returned within 2 seconds
- **NFR4:** SQLite queries against the shipments table must complete within 100ms for all indexed columns
- **NFR5:** The frontend must display a loading indicator within 300ms of any user-initiated action to prevent perceived unresponsiveness
- **NFR6:** The Vercel frontend must load and render the initial SPA within 5 seconds on a cold start

### Security

- **NFR7:** All SQL executed against the database must be generated by the LLM and validated by the Verifier layer — no raw user input is interpolated directly into SQL strings
- **NFR8:** The Verifier layer must reject any generated SQL containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, or `ALTER` statements targeting the `shipments` table
- **NFR9:** All frontend-to-backend communication must occur over HTTPS — enforced by Vercel (frontend) and Render (backend) TLS termination
- **NFR10:** API keys and secrets must be stored as environment variables only — never committed to the repository

### Integration

- **NFR11:** The system must handle OpenRouter API unavailability gracefully — returning a structured error response within 5 seconds of connection timeout rather than hanging indefinitely
- **NFR12:** The backend must initialise successfully from a cold Render deploy within 60 seconds, including CSV load and schema creation
- **NFR13:** The response cache must be keyed by a SHA-256 hash of the full request payload (model + messages + temperature) to ensure cache correctness across prompt changes
- **NFR14:** The `/api/health` endpoint must respond within 500ms and accurately reflect database connectivity and OpenRouter reachability at the time of the request
- **NFR15:** PyMuPDF PDF-to-image conversion must complete within 5 seconds for documents up to 10 pages before passing to the vision model

### Known Constraints

- SQLite is single-writer; concurrent API requests may serialise on DB writes (acceptable at POC scale)
- Render free tier has ephemeral disk — `extracted_documents` data does not persist across deploys
- OpenRouter free tier rate limit (50 req/day) means the system is not suitable for high-volume demo sessions without cache warming
- Vision extraction quality degrades for documents with heavy rotation, low resolution, or non-Latin scripts
