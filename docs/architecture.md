# FreightMind — Architecture

## System Overview

FreightMind is a two-part AI platform deployed as a multi-container application.

```
frontend/   Next.js 16 · TypeScript · Tailwind CSS
backend/    Python 3.12 · FastAPI · SQLAlchemy · SQLite
```

Both parts share a single SQLite database file (`freightmind.db`). All three agents read from and write to the same data store — this is the non-negotiable Part 1 → Part 2 linkage requirement.

---

## Agent Architecture: Planner → Executor → Verifier

All agents follow the same three-layer pattern:

```
Planner     — prepares input, classifies intent, normalises data
Executor    — calls the LLM / executes the operation
Verifier    — validates output, enforces safety, scores confidence
```

This separation means each layer is independently testable.

---

## Backend Module Map

```
backend/app/
├── agents/
│   ├── analytics/
│   │   ├── planner.py      NL → intent classification + SQL plan
│   │   ├── executor.py     SQL generation + auto-repair (SQLite syntax)
│   │   └── verifier.py     Read-only SQL guard (rejects DDL/DML)
│   ├── extraction/
│   │   ├── planner.py      PDF/image → PNG bytes (via PyMuPDF)
│   │   ├── executor.py     Base64 image → vision LLM → raw JSON
│   │   ├── verifier.py     Field validation + confidence scoring
│   │   └── normaliser.py   Rule-based field normalisation (dates, weights, modes, countries)
│   └── verification/           ← Part 2
│       ├── comparator.py   Customer rules loading + field comparison (separate module)
│       ├── drafter.py      LLM-powered draft email generation
│       └── pipeline.py     Trigger → Extract → Compare → Flag → Draft orchestrator
├── api/routes/
│   ├── analytics.py        POST /api/query, GET /api/schema, GET /api/stats/live
│   ├── documents.py        POST /extract, POST /confirm, GET /pending, GET /extractions, DELETE
│   ├── verification.py     POST /verify/submit, GET /verify/result/{id}, GET /verify/queue
│   ├── system.py           GET /api/health
│   └── demo.py             Demo-only endpoints
├── models/
│   ├── shipment.py
│   ├── extracted_document.py   ← extended in Part 2 (5 new trade fields)
│   ├── extracted_line_item.py
│   └── verification_result.py  ← Part 2 (verification_results + verification_fields tables)
├── schemas/
│   ├── analytics.py
│   ├── documents.py
│   ├── verification.py         ← Part 2
│   └── common.py
├── services/
│   ├── model_client.py     Unified LLM caller: caching + retry + fallback
│   ├── stats_service.py    IQR-based anomaly detection + baseline cache
│   └── data_seeder.py      Synthetic data generation for demo
├── core/
│   ├── config.py           Pydantic settings (all values from .env)
│   ├── database.py         SQLAlchemy engine + init_db() + Part 2 migrations
│   └── prompts.py          Prompt file loader (from backend/app/prompts/*.txt)
└── prompts/
    ├── extraction_system.txt
    ├── extraction_fields.txt       ← extended in Part 2 (5 new fields added)
    ├── verification_draft.txt      ← Part 2
    ├── analytics_system.txt
    ├── analytics_sql_gen.txt
    └── analytics_answer.txt
```

---

## Part 2: Verification Pipeline

```
Trigger (POST /api/verify/submit)
    │
    ▼
[Validate file — no content / bad type → _store_failed()]
    │
    ▼
ExtractionPlanner.prepare()     PDF → PNG
    │
    ▼
ExtractionExecutor.extract()    Vision LLM → raw JSON
    │  [LLM failure after retries → _store_failed()]
    ▼
ExtractionVerifier.score_confidence()    String confidence → float
    │  [Malformed output → coerced to LOW → uncertain in comparator]
    ▼
load_customer_rules(customer_id)    JSON config file
    │  [Config missing → _store_failed()]
    ▼
DocumentComparator.compare()    Field-by-field: match | mismatch | uncertain | no_rule
    │  [confidence < threshold → uncertain, even if value matches]
    ▼
DocumentComparator.determine_overall_status()
    │  mismatch present → amendment_required
    │  uncertain present → uncertain
    │  all match/no_rule → approved
    ▼
VerificationDrafter.generate()    LLM draft email (with template fallback)
    │
    ▼
Persist to SQLite (verification_results + verification_fields)
    │
    ▼
Return VerificationResultResponse → UI renders 4 states
```

### Failure Scenarios (from assignment spec)

| Scenario | Handler |
|---|---|
| HS code partially obscured | Vision LLM returns LOW confidence → comparator marks `uncertain` → not approved |
| LLM returns unrecognised format | `score_confidence` coerces to LOW → comparator marks `uncertain` |
| Customer config missing rule for field | Comparator marks field `no_rule` — surfaced in UI, not auto-approved |
| No attachment / corrupted file | `_store_failed()` called immediately — no partial result stored |
| LLM API fails / times out | ModelClient retries once internally; on persistent failure → `_store_failed()` — CG notified, no crash |

---

## ModelClient

`backend/app/services/model_client.py` is the unified LLM caller used by all three agents.

| Feature | Detail |
|---|---|
| Caching | SHA-256 keyed file cache under `./cache/` — bypassed if `BYPASS_CACHE=true` |
| Retry | Up to 3 retries with exponential backoff (1s → 2s → 4s) |
| Fallback | If primary model fails all retries, tries `_fallback` model |
| Rate limiting | Parses `retry-after` header, raises `RateLimitError` with wait time |
| Timeout | Configurable per call type (vision: 120s default, analytics: 60s default) |

---

## Customer Rules Configuration

```
backend/config/customer_rules/
└── DEMO_CUSTOMER_001.json
```

Each customer has its own JSON file. The pipeline loads by `customer_id`. Swapping customers means swapping config files — no agent code changes needed.

**Config structure:**
```json
{
  "customer_id": "DEMO_CUSTOMER_001",
  "customer_name": "GlobalTech Industries",
  "rules": {
    "hs_code":          { "expected": "8471.30.00", "match_type": "exact", "description": "..." },
    "incoterms":        { "expected": "CIF",         "match_type": "exact", "description": "..." },
    "consignee_name":   { "expected": "GlobalTech Industries Ltd.", "match_type": "contains", "description": "..." },
    "port_of_loading":  { "expected": "Shanghai",   "match_type": "contains", "description": "..." },
    "port_of_discharge":{ "expected": "Rotterdam",  "match_type": "contains", "description": "..." },
    "shipment_mode":    { "expected": "Ocean",       "match_type": "exact", "description": "..." },
    "origin_country":   { "expected": "China",       "match_type": "contains", "description": "..." }
  },
  "confidence_thresholds": {
    "uncertain_below": 0.6,
    "low_confidence_value": 0.3
  }
}
```

`match_type: "exact"` → case-insensitive equality
`match_type: "contains"` → case-insensitive substring match (either direction)

---

## Database Migration Strategy

SQLAlchemy's `create_all()` creates missing tables but does not add columns to existing tables. Part 2 added 5 columns to `extracted_documents`. The migration runs in `init_db()` using `ALTER TABLE ... ADD COLUMN` wrapped in try/except — safe to run repeatedly on an existing DB.

---

## Frontend: `/verification` Route

Separate Next.js route at `/verification` — not a tab on the main page.

**State machine:**
```
idle → incoming (processing spinner) → result
                                         ├── status banner (approved / amendment_required / uncertain / failed)
                                         ├── field verification table (clickable rows for mismatch/uncertain)
                                         │       └── discrepancy detail panel (extracted vs expected + rule)
                                         └── draft reply (editable textarea + send/reset buttons)
```

**Confidence visualization:**
- ≥ 0.8 → green bar + "High"
- 0.5–0.79 → amber bar + "Medium"
- < 0.5 → red bar + "Low"

**Field status badges:**
- `match` → green
- `mismatch` → red (clickable, expands discrepancy)
- `uncertain` → amber (clickable, expands discrepancy)
- `no_rule` → grey

---

## Trigger Mechanism

The assignment allows a folder watcher or CLI trigger. FreightMind uses an API endpoint:

```
POST /api/verify/submit
  file: multipart upload (PDF/PNG/JPEG)
  customer_id: form field (default: DEMO_CUSTOMER_001)
```

This simulates an SU email arriving with an attached trade document. A folder watcher, email integration (e.g. AWS SES webhook), or any other trigger mechanism would call this same endpoint. Documented in README.
