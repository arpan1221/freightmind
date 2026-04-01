# FreightMind — Demo 04: Anomaly Detection — Ocean Cost Spike (≤ 2 min)

Seed 35 Ocean shipments with freight costs ~1.7× the historical mean, then watch the freight cost anomaly surface in analytics responses.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**. Independent of Demo 03 — can run in any order.

---

## Step 1 — Baseline Ocean freight cost (~15 s)

In the **Chat** panel, type:

```
What is the average freight cost for Ocean shipments?
```

**Expected output:** ~$12,700–$14,000 range. Clean answer, no anomaly note.

**What to point out:**
- Result falls within the IQR fence for `freight_cost_usd_ocean` (~$28,875 upper boundary)
- System stays quiet

---

## Step 2 — Seed the scenario (~10 s)

In a terminal:

```bash
curl -s -X POST http://localhost:8000/api/demo/seed/ocean_cost_spike \
  | python3 -m json.tool
```

**Expected response:**
```json
{
  "scenario": "ocean_cost_spike",
  "rows_inserted": 35,
  "stats_refreshed": true
}
```

**What to point out:**
- 35 Ocean shipments seeded with freight costs $24k–$48k (vs historical mean ~$12.7k)
- Stats cache refreshed — new distribution reflects the spike

---

## Step 3 — Compare all modes — anomaly surfaces (~20 s)

Type:

```
Compare average freight cost across all shipment modes
```

**Expected output:** Mode × avg_cost table. Ocean now stands elevated above its historical baseline.

**What to point out:**
- If the Ocean average crosses the IQR fence, the answer includes an anomaly note
- The hypothesis may reference supply chain disruption, re-routing, or fuel surcharges

---

## Step 4 — Drill into the spike (~20 s)

Type:

```
Show the top 10 most expensive Ocean shipments by freight cost
```

**Expected output:** Top 10 rows — seeded high-cost rows appear at the top with 2025–2026 delivery dates.

**What to point out:**
- Delivery dates in 2025–2026 distinguish synthetic rows from SCMS 2006–2015 data
- SQL disclosure shows `WHERE shipment_mode = 'Ocean' ORDER BY freight_cost_usd DESC LIMIT 10`

---

## Total: ~65 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Baseline | System quiet before spike | Engineering depth |
| Step 2 — Seed | Freight cost distribution perturbed | Engineering depth |
| Step 3 — Mode comparison | Anomaly fires on freight cost dimension | Engineering depth |
| Step 4 — Drill-down | Seeded rows visible and distinguishable | Behaviour A |
