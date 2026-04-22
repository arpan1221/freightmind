# FreightMind — Documentation Index

**Generated:** 2026-04-09  
**Scan level:** Deep  
**Project type:** Multi-part (Python/FastAPI backend + Next.js frontend)  
**Assignment:** GoComet AI Solutions Engineer DAW — Parts 1 & 2

---

## Quick Links

| Document | Description |
|---|---|
| [Project Overview](./project-overview.md) | What FreightMind is, the three users, what was built |
| [Architecture](./architecture.md) | Agent design, module map, pipeline flows, DB migration strategy |
| [Architecture Diagrams](./architecture-diagrams.md) | Mermaid diagrams: system overview + 3 pipeline sequences |
| [Data Models](./data-models.md) | All 6 DB tables with column definitions, confidence mapping |
| [API Reference](./api-reference.md) | All 12 endpoints with request/response schemas and error types |
| [Part 2: Verification Workflow](./part2-verification-workflow.md) | SU→CG workflow detail: pipeline steps, failure scenarios, UI states |
| [Setup Guide](./setup-guide.md) | Local dev, Docker, env vars, adding new customers |
| [Demo Script](./demo-script.md) | 2-minute walkthrough: analytics → extraction → verification → history query |

---

## BMAD Planning Artifacts

| Artifact | Description |
|---|---|
| [Part 2 PRD](./../_bmad-output/planning-artifacts/part2-prd.md) | Retroactive PRD for Part 2: problem, goals, FRs, NFRs, acceptance criteria, stories |

---

## Existing Reference Docs

| Document | Description |
|---|---|
| [README.md](./../README.md) | Top-level setup, architecture overview, sample questions |
| [TECH_DECISIONS.md](./../TECH_DECISIONS.md) | Engineering decision log (model selection, DB choice, etc.) |
| [DATASET_SCHEMA.md](./../DATASET_SCHEMA.md) | SCMS shipment CSV schema (42 columns) |

---

## Project Structure Summary

```
freightmind/
├── backend/                    Python 3.12 · FastAPI · SQLAlchemy · SQLite · PyMuPDF
│   ├── app/agents/
│   │   ├── analytics/          Planner → Executor → Verifier (NL→SQL)
│   │   ├── extraction/         Planner → Executor → Verifier (vision extraction)
│   │   └── verification/       Comparator · Drafter · Pipeline (Part 2)
│   ├── app/api/routes/         analytics · documents · verification · system · demo
│   ├── app/models/             shipment · extracted_document · extracted_line_item · verification_result
│   ├── app/prompts/            LLM prompt templates (configurable, not buried in code)
│   ├── config/customer_rules/  Per-customer rule JSON configs (Part 2)
│   └── freightmind.db          Shared SQLite DB (all 6 tables)
├── frontend/                   Next.js 16 · TypeScript · Tailwind CSS · Axios
│   └── src/app/
│       ├── page.tsx            / — Analytics + Documents tabs (Part 1)
│       └── verification/       /verification — CG verification UI (Part 2)
├── demo/                       Sample PDFs + demo scripts
├── scripts/                    create_sample_invoices.py
└── docs/                       ← you are here
```

---

## Key Design Decisions

- **Shared SQLite DB** — analytics agent queries verification history without any changes
- **Planner → Executor → Verifier** — all three agents follow the same separation pattern
- **Confidence thresholds in config** — no magic numbers in code; configurable per customer
- **No silent approvals** — low-confidence extractions are `uncertain` regardless of value match
- **Template fallback on LLM failure** — draft is always produced; pipeline never crashes
- **Agent never sends** — CG always controls the final send action
