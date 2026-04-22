# FreightMind — Project Overview

## What It Is

FreightMind is an AI-powered freight intelligence platform built as a two-part hiring assignment for a GoComet AI Solutions Engineer role.

It solves two real problems in freight logistics:

1. **Business users can't query freight data without an analyst** — FreightMind's analytics agent lets anyone ask natural language questions against a 10,000+ row shipment dataset and get back grounded answers with the SQL used and a chart.

2. **Document verification is entirely manual** — The SU → CG workflow (Shipping Unit sends trade docs, Cargo Control Group validates them field-by-field against customer requirements) is slow and error-prone. FreightMind automates extraction, comparison, flagging, and draft reply generation.

---

## Assignment Context

| Item | Detail |
|---|---|
| Role | AI Solutions Engineer (3–5 years experience) |
| Issuer | GoComet |
| Part 1 | Agentic Analytics + Vision Document Extraction (24 hrs) |
| Part 2 | Agentic Document Verification — SU → CG workflow (3–4 hrs) |
| Evaluation | Each part evaluated separately, combined for final decision |

Part 2 is not independent — it extends the extraction and analytics agents built in Part 1.

---

## The Three Users

| Role | Who | What They Need |
|---|---|---|
| **SU** (Shipping Unit) | Supplier / shipper | Send trade docs (Bill of Lading, Commercial Invoice, Packing List, Certificate of Origin) |
| **CG** (Cargo / Control Group) | Validator | Receive SU docs, check every field against customer requirements, approve or request amendments |
| **Customer** | End recipient | Receive one clean, correct document set — errors cause customs delays and contract penalties |

---

## What Was Built

### Part 1

- **Agentic Analytics Layer** — natural language → SQL → grounded answer + chart + transparency (SQL shown)
- **Vision Document Agent** — PDF/image → structured field extraction with per-field confidence scores
- **End-to-End Linkage** — extracted documents stored in same SQLite DB, queryable via the analytics agent

### Part 2

- **SU → CG Verification Pipeline** — trigger → extract (reuses Part 1) → compare against customer rules → flag discrepancies → draft reply
- **CG Verification UI** — 4-state interface: Incoming, Verification Result, Discrepancy Detail, Draft Reply
- **Customer Rules Config System** — rules stored in JSON per customer; swapping customers = swapping config file
- **Verification History** — all results persisted to SQLite; Part 1 analytics can answer "which fields failed most often this week?"

---

## Key Design Principles

- **No silent approvals** — low-confidence extractions are marked uncertain regardless of whether the value appears to match
- **Fail loud, not silently** — all 5 failure scenarios store a failed record and notify CG; no crashes
- **Transparency** — every analytics answer shows the SQL used; every extraction shows field-level confidence
- **Agent never sends** — the draft reply is always editable by CG before any action is taken
- **Separation of concerns** — extraction, comparison, analytics are independently runnable modules
