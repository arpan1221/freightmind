# FreightMind — Demo Scripts

Ten focused scripts covering every capability of the system.
Each script is self-contained and playable in the order shown, or independently.

| # | Script | Duration | Covers |
|---|--------|----------|--------|
| 01 | [Basic SCMS Analytics](demo-01-basic-scms-analytics.md) | ~2 min | NL→SQL, charts, SQL disclosure, follow-ups |
| 02 | [Anomaly Baseline](demo-02-anomaly-detection-baseline.md) | ~1 min | System stays quiet on unremarkable queries |
| 03 | [Nigeria Air Surge](demo-03-anomaly-nigeria-air-surge.md) | ~2 min | Seed + anomaly fires on Air count |
| 04 | [Ocean Cost Spike](demo-04-anomaly-ocean-cost-spike.md) | ~2 min | Seed + freight cost anomaly |
| 05 | [New Vendor Emergence](demo-05-anomaly-new-vendor.md) | ~2 min | Seed + vendor count anomaly |
| 06 | [Vision Extraction — High Confidence](demo-06-vision-extraction-high.md) | ~2 min | Upload, confidence badges, confirm |
| 07 | [Vision Extraction — Edge Cases](demo-07-vision-extraction-edges.md) | ~2 min | NOT_FOUND, LOW confidence badges |
| 08 | [Cross-Table Linkage](demo-08-cross-table-linkage.md) | ~2 min | Confirmed invoice vs SCMS dataset |
| 09 | [Failure Handling](demo-09-failure-handling.md) | ~1 min | Unsafe SQL rejection, error toast |
| 10 | [Full Submission Demo](demo-10-full-submission-demo.md) | ~90 sec | Complete end-to-end for recording |

## Prerequisites

Stack running:
```bash
cp .env.example .env   # add OPENROUTER_API_KEY
docker compose up --build
```

- Frontend: http://localhost:3000
- API / Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Demo invoices live in `backend/data/demo_invoices/`.
