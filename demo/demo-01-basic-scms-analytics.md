# FreightMind — Demo 01: Basic SCMS Analytics (≤ 2 min)

Natural-language analytics over 10,324 historical SCMS shipment records: SQL generation, result tables, charts, and follow-up suggestions.

---

## 0. Prerequisites

Stack running (`docker compose up --build`), browser open at **http://localhost:3000**. No prior setup needed.

---

## Step 1 — Country-level aggregate with chart (~25 s)

In the **Chat** panel, type:

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
- Streamed text answer followed by a result table and bar chart
- Expand **SQL ▶** — evaluator sees the generated `SELECT … GROUP BY … ORDER BY … LIMIT 5`
- Three follow-up suggestion chips appear below the answer

---

## Step 2 — Vendor cost analysis with NULL disclosure (~25 s)

Type:

```
Which vendors have the highest average freight cost per kg for Air shipments?
```

**Expected output:** Ranked vendor table with `avg_cost_per_kg`.

**What to point out:**
- The answer includes a note on rows excluded due to `NULL weight_kg` or `NULL freight_cost_usd` — transparent about what was filtered
- SQL disclosure shows the `IS NOT NULL` guard the Executor added automatically

---

## Step 3 — Temporal trend (~25 s)

Type:

```
Show monthly shipment volume for 2014 broken down by shipment mode
```

**Expected output:** Month × mode breakdown rendered as a **line chart**.

**What to point out:**
- Chart type switches from bar to line because the result is a time series — the chart generator infers this
- The LLM translated "monthly … 2014" into the correct date truncation in SQL without guidance

---

## Total: ~75 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Country aggregate | NL → SQL → table + bar chart | Behaviour A |
| Step 2 — Vendor cost + NULLs | NULL exclusion transparency | Behaviour A |
| Step 3 — Temporal trend | Adaptive chart type | Behaviour A |
