# FreightMind — Demo 05: Anomaly Detection — New Vendor Emergence (≤ 2 min)

Seed 25 shipments from a brand-new vendor absent from the SCMS dataset, then surface it through vendor analytics.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**. Independent of other seeding demos.

---

## Step 1 — Vendor landscape baseline (~20 s)

In the **Chat** panel, type:

```
Who are the top 10 vendors by total shipment count?
```

**Expected output:** Ranked vendor table. `FreightCo International` does not appear.

**What to point out:**
- All vendors are drawn from the 2006–2015 SCMS dataset
- No mention of FreightCo International

---

## Step 2 — Seed the scenario (~10 s)

In a terminal:

```bash
curl -s -X POST http://localhost:8000/api/demo/seed/new_vendor_emergence \
  | python3 -m json.tool
```

**Expected response:**
```json
{
  "scenario": "new_vendor_emergence",
  "rows_inserted": 25,
  "stats_refreshed": true
}
```

**What to point out:**
- 25 shipments from `FreightCo International` seeded across Air, Ocean, and Truck modes
- This vendor did not exist in the SCMS dataset — it is a genuinely new actor

---

## Step 3 — Vendor query with new entrant (~20 s)

Type:

```
Who are the top 10 vendors by total shipment count?
```

**Expected output:** `FreightCo International` now appears in the list with 25 shipments.

**What to point out:**
- A vendor that didn't exist 30 seconds ago is now visible in the analytics
- If its count exceeds the IQR fence for `count_per_vendor_all`, an anomaly note appears

---

## Step 4 — Isolate the new vendor (~15 s)

Type:

```
Show all shipments handled by FreightCo International
```

**Expected output:** 25 rows, all with `scheduled_delivery_date` in 2025–2026.

**What to point out:**
- Delivery dates distinguish new synthetic shipments from SCMS historical data
- SQL disclosure shows `WHERE vendor = 'FreightCo International'`

---

## Total: ~65 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Baseline | New vendor absent before seeding | Engineering depth |
| Step 2 — Seed | Novel actor inserted into live dataset | Engineering depth |
| Step 3 — Vendor query | New entrant surfaces in analytics | Engineering depth |
| Step 4 — Isolation | Date-distinguishable synthetic rows | Behaviour A |
