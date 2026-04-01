# FreightMind — Demo Scripts

## Master Demo

**[demo-00-master.md](demo-00-master.md)** — Start here. Covers all three required behaviours and failure handling in a single ~2 min flow. This is the script to use for evaluation.

---

## Scenario Scripts

Individual scripts for exploring each capability in depth.

| # | Script | Duration | Covers |
|---|--------|----------|--------|
| 01 | [Basic SCMS Analytics](demo-01-basic-scms-analytics.md) | ~2 min | NL→SQL, charts, SQL disclosure, NULL transparency |
| 02 | [Anomaly Baseline](demo-02-anomaly-detection-baseline.md) | ~1 min | System stays quiet on unremarkable queries |
| 03 | [Nigeria Air Surge](demo-03-anomaly-nigeria-air-surge.md) | ~2 min | Manual seed → anomaly fires on Air count |
| 03b | [Live Seeding](demo-03b-live-seeding.md) | ~2 min | Background drip seeder, counter ticks, anomaly surfaces naturally |
| 04 | [Ocean Cost Spike](demo-04-anomaly-ocean-cost-spike.md) | ~2 min | Manual seed → freight cost anomaly |
| 05 | [New Vendor Emergence](demo-05-anomaly-new-vendor.md) | ~2 min | Manual seed → new actor in vendor landscape |
| 06 | [Vision Extraction — High Confidence](demo-06-vision-extraction-high.md) | ~2 min | Upload, HIGH badges, confirm, query |
| 07 | [Vision Extraction — Edge Cases](demo-07-vision-extraction-edges.md) | ~2 min | NOT_FOUND, LOW confidence, non-Latin scripts |
| 08 | [Cross-Table Linkage](demo-08-cross-table-linkage.md) | ~2 min | Confirmed invoice vs SCMS dataset |
| 09 | [Failure Handling](demo-09-failure-handling.md) | ~1.5 min | Unsafe SQL, out-of-scope, empty state |

---

## Live Seeding vs Controlled Seeding

| Mode | When to use | How to set |
|------|-------------|------------|
| **Controlled** (default) | Demos 00, 03–05 — explicit before/after contrast | `LIVE_SEEDING_INTERVAL_SECONDS=0` |
| **Live** | Demo 03b — data ticks up automatically, anomalies surface without manual triggers | `LIVE_SEEDING_INTERVAL_SECONDS=30` |

Do not mix modes in the same session — live seeding will seed rows before the "baseline" step in demos 03–05 and collapse the before/after contrast.

---

## Prerequisites

Stack running:
```bash
cp .env.example .env   # add OPENROUTER_API_KEY
docker compose up --build
```

- Frontend: http://localhost:3000
- API / Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Demo invoices: `backend/data/demo_invoices/`
