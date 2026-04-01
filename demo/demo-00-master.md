# FreightMind — Master Demo (≤ 2 min)

Covers all three required behaviours and the failure handling criterion in a single continuous flow.

**A — Agentic Analytics · B — Vision Extraction · C — End-to-End Linkage · Failure Handling**

---

## 0. Prerequisites

Stack running (`docker compose up --build`), browser open at **http://localhost:3000**.  
`LIVE_SEEDING_INTERVAL_SECONDS=0` (default) — controlled seeding only.  
Terminal window open alongside the browser.

---

## Step 1 — Analytics on SCMS shipments data (~25 s)

In the **Analytics** tab, type:

```
What are the top 5 destination countries by number of Air shipments?
```

**Expected output**

| country | count |
|---------|-------|
| Vietnam | 687 |
| Côte d'Ivoire | 682 |
| Haiti | 560 |
| Nigeria | 547 |
| Uganda | 534 |

**What to point out:**
- Streamed text answer with grounded numbers from 10,324 SCMS records
- Result table and bar chart rendered beneath the answer
- Expand **SQL ▶** — show the generated `SELECT … GROUP BY … ORDER BY … LIMIT 5`
- Follow-up suggestion chips appear below the answer

---

## Step 2 — Statistical judgment layer (~20 s)

In a terminal:

```bash
curl -s -X POST http://localhost:8000/api/demo/seed/nigeria_air_surge | python3 -m json.tool
```

Then type the same question again:

```
What are the top 5 destination countries by number of Air shipments?
```

**Expected output:** Nigeria moves up to position 3 with 589. The answer may include an anomaly note on one of the top countries — the agent flags whichever country's count deviates most from its own historical distribution, e.g.:

> *"[Country]'s Air shipment count is statistically unusual — above the typical ceiling for that destination. This may reflect cold chain requirements or port congestion forcing modal shift."*

**What to point out:**
- Same question, different answer shape — the agent detected a change in the data
- The agent determines which country is anomalous based on each country's own baseline, not a global threshold — it may not be Nigeria
- The hypothesis is freight-domain specific, not a generic statistical comment
- No alert was pre-configured — the system modelled its own distribution

---

## Step 3 — Vision extraction with confidence badges (~25 s)

Switch to the **Documents** tab. Upload:

```
backend/data/demo_invoices/demo-01-air-nigeria-linkage.pdf
```

**Expected output:** Extraction table with HIGH badges on all key fields.

| Field | Value | Badge |
|-------|-------|-------|
| shipment_mode | Air | HIGH |
| destination_country | Nigeria | HIGH |
| weight_kg | 285.0 | HIGH |
| freight_cost_usd | 8,920.00 | HIGH |

**What to point out:**
- Loading indicator while the vision model processes page 1 of the PDF
- GREEN HIGH badges on clearly legible fields — each field scored independently
- Click **Confirm** to persist the extraction to the database

---

## Step 4 — Cross-table linkage query (~20 s)

Switch back to the **Analytics** tab and type:

```
Compare the freight cost from my confirmed invoice against the average freight cost for Air shipments to Nigeria in the dataset
```

**Expected output**

| Source | Freight Cost USD |
|--------|-----------------|
| Confirmed invoice | 8,920.00 |
| Dataset average — Air / Nigeria | ~17,662 |

**What to point out:**
- Expand **SQL ▶** — the query references **both** `shipments` and `extracted_documents`
- The user's document is analytically comparable to the historical Air shipments to Nigeria in the dataset
- This is the A → B linkage: extraction and analytics share the same database

---

## Step 5 — Failure handling (~15 s)

Type:

```
Delete all shipments where the country is Nigeria
```

**Expected output:** Error toast — *"The generated query was not allowed. Only read-only SELECT queries are permitted."*

**What to point out:**
- The Verifier rejected the SQL before it reached the database
- No data was modified — this is a hard architectural guard
- The rejected SQL is shown in the disclosure for full transparency

---

## Total: ~105 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Analytics | NL → SQL → table + chart + follow-ups | Behaviour A |
| Step 2 — Anomaly | Self-aware statistical judgment layer | Engineering depth |
| Step 3 — Extraction | Vision → confidence badges → confirm | Behaviour B |
| Step 4 — Linkage | SQL references both `shipments` and `extracted_documents` | Behaviour C |
| Step 5 — Failure | Verifier rejects unsafe SQL before execution | Failure handling (25 %) |
