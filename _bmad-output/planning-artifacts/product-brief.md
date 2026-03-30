# Product Brief: FreightMind

**Type:** Technical POC — GoComet AI Solutions Engineer Take-Home Assignment (Part 1)
**Timeline:** <48 hours
**Evaluators:** GoComet Engineering/Product Team

---

## Executive Summary

FreightMind is a proof-of-concept agentic AI platform that bridges the two most common data problems in logistics operations: business users who can't query structured shipment records without analyst help, and operations teams who can't extract structured data from freight invoices without manual entry. Two AI agents — an Agentic Analytics agent and a Vision Document Extraction agent — share a single SQLite data store, enabling queries that span both pre-loaded historical records and freshly extracted invoice data in the same conversation.

The POC is built to be runnable from a public URL on day one: a Next.js frontend on Vercel, a FastAPI backend on Render, and a pre-loaded dataset of 10,324 real shipment records from the USAID Supply Chain Management System (SCMS) — health commodity logistics data covering freight modes, costs, weights, vendors, and delivery timelines across 15+ countries. The freight mechanics (shipment mode, cost per kg, delivery delay, vendor performance) are domain-agnostic and directly applicable to commercial freight contexts. No local setup is required for the evaluator. The system surfaces its reasoning at every step — generated SQL is shown, extraction confidence is scored per field, and every failure path returns a structured, honest response rather than a silent error or hallucinated answer.

The stack is chosen to demonstrate production thinking within real constraints: zero API budget (OpenRouter free tier), limited rate headroom (50 req/day), and a sub-48-hour build window around existing work commitments.

---

## The Problem

Logistics companies sit on rich structured data — shipment records, cost breakdowns, delivery timelines, vendor performance — but that data is locked behind analysts who can write SQL. Business users wait hours or days for answers to questions like "Which carrier had the worst on-time rate to Nigeria last quarter?" or "What's our average freight cost per kg by shipment mode?" Meanwhile, the documents that generate that data — freight invoices, bills of lading, delivery receipts — are processed manually, creating a permanent lag between document receipt and queryable data.

The two problems compound each other. Analytics is blocked on structured data that never fully reflects what's in the documents. Document processing is manual because there's no AI pipeline to route extracted data into the analytics store.

---

## The Solution

FreightMind connects both ends. Two independently operable agents share a data store and can be queried together:

**Agentic Analytics Agent:** Accepts natural language questions, generates validated SQL against a schema-aware prompt, executes the query, and returns a structured response: text answer + raw SQL + result table + chart configuration. Follow-up questions maintain context. Unanswerable questions get an honest explanation of what the data does and doesn't cover.

**Vision Document Extraction Agent:** Accepts PDF or image uploads of freight invoices. Converts to a format the vision LLM can process, extracts 14 structured fields plus line items, scores each field's confidence (HIGH/MEDIUM/LOW), and presents the result to the user for review before storing. LOW-confidence fields are visually flagged — never silently accepted.

**End-to-End Linkage:** Extracted documents land in the same SQLite database as the historical shipment records. The analytics agent is schema-aware of both tables, enabling UNION queries like "Compare the freight cost of my uploaded invoices to the dataset average for that shipment mode" — a concrete, demonstrable proof that both agents are genuinely connected.

---

## What Makes This Different

**Honest failure handling is the core differentiator.** Most demos hide failure cases. FreightMind surfaces them: malformed LLM output triggers a structured retry; missing invoice fields are flagged as "NOT FOUND" rather than omitted; out-of-scope questions return a clear explanation of what data is available. Failure handling is 25% of the evaluation score — this is built as a first-class concern, not an afterthought.

**Transparency over magic.** Every analytics response shows the SQL that was generated and executed. Every extracted document shows per-field confidence. The `/api/schema` endpoint exposes the full database schema for evaluator inspection. The reasoning is never hidden.

**Real architectural layers, not a single script.** A Planner routes intent; Executors specialize by task; a Verifier validates SQL and extraction output before anything touches the database; a Model Abstraction Layer handles fallbacks, retries, and caching. This maps to how you'd actually build an agentic system at production scale — not just a chain of LLM calls.

**Production deployment, not local-only.** The evaluator clicks a URL. Nothing to install.

---

## Who This Serves

**Primary:** GoComet engineering evaluators assessing AI Solutions Engineer candidates. Success looks like: "This person understands agentic systems, builds defensively, and ships something that actually runs."

**Demonstrated user persona:** A logistics operations analyst at a freight company who needs to query shipment performance data without writing SQL, and who receives physical or digital freight invoices that currently require manual data entry.

---

## Success Criteria

| Criterion | Target |
|-----------|--------|
| End-to-end system works on fresh load | Both agents respond correctly to demo queries from a clean environment |
| Failure paths return structured responses | 0 unhandled exceptions surfaced to the user |
| SQL transparency | Every analytics response includes the query used |
| Extraction confidence | Every field has a confidence score; LOW fields are visually flagged |
| Linkage query works | At least one cross-table query returns correct results |
| Evaluator score | Pass the assignment; receive a follow-up for Part 2 |

---

## Scope

**In — Part 1:**
- Analytics agent: NL → SQL → execute → format (text + table + chart)
- Vision extraction agent: PDF/image → extract → confidence score → review → store
- End-to-end linkage: cross-table queries spanning `shipments` + `extracted_documents`
- Failure handling: malformed LLM output, missing fields, unanswerable questions, rate limits, model fallbacks
- Deployed and publicly accessible (Vercel + Render)
- 5-6 synthetic freight invoices for demonstration
- README with architecture overview and demo script

**Out — Part 1:**
- Authentication / user roles (Part 2 concern)
- Real-time streaming (SSE)
- Production database (Postgres, etc.)
- Automated test suite beyond manual demo validation
- Mobile-optimized UI

---

## Technical Approach (Summary)

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | Next.js 14 + TypeScript + Tailwind → Vercel | Production signal; zero-friction evaluator access |
| Backend | FastAPI (Python 3.11) → Render | Async LLM calls; auto OpenAPI docs; Python AI ecosystem |
| Dataset | USAID SCMS (10,324 rows) | Clean freight mechanics data; sentinel values in cost/weight columns used as intentional null-handling demonstration |
| Database | SQLite | Zero infra; shared store for linkage; assignment-approved |
| LLM (text/SQL) | Llama 3.3 70B via OpenRouter | Free tier; strong SQL generation; fallback to DeepSeek R1 |
| LLM (vision) | Qwen3 VL 235B via OpenRouter | Best free vision model; fallback to Nemotron Nano VL |
| Caching | File-based hash cache | Non-negotiable given 50 req/day free tier limit |
| PDF processing | PyMuPDF | No system dependencies; works on Render without extras |
| Charts | Recharts | React-native; simple API for bar/line/pie |

---

## Vision

If Part 1 passes, Part 2 extends this into a multi-role verification workflow: Shipping Units submit extracted documents, Cargo Graders verify them. The architecture is designed for this — `confirmed_by_user` and `extracted_at` fields are already in the schema, the review-before-commit flow is modular, and the confirmation endpoint accepts corrections before storage.

Beyond the assignment: this architecture pattern — agentic analytics over structured data, vision extraction over documents, shared queryable store, honest failure handling — is directly applicable to GoComet's core product challenges in freight visibility and document digitization.
