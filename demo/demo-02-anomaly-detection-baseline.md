# FreightMind — Demo 02: Anomaly Detection Baseline (≤ 1 min)

Establishes that the statistical judgment layer stays silent on unremarkable queries — selective voice before triggering anomalies in Demos 03–05.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**. Run **before** any seeding scenarios.

---

## Step 1 — Mode distribution (~15 s)

In the **Chat** panel, type:

```
How many shipments are there by shipment mode?
```

**Expected output:** Air, Ocean, Truck, Air Charter counts. Clean answer, no anomaly note.

**What to point out:**
- Plain, direct answer — the system has nothing unusual to report
- No "Statistical Anomaly Detected" block appears — the system is quiet

---

## Step 2 — Average freight cost (~15 s)

Type:

```
What is the average freight cost for Truck shipments?
```

**Expected output:** A dollar figure in the $13,000–15,000 range. No anomaly note.

**What to point out:**
- The result falls within the IQR fence for `freight_cost_usd_truck`
- The judgment layer checked the stats cache and chose not to speak

---

## Step 3 — Confirm the stats cache is live (~10 s)

In a terminal:

```bash
curl -s http://localhost:8000/api/stats/live | python3 -m json.tool
```

**Expected output:**
```json
{
  "shipments": 10324,
  "extracted_documents": 0,
  "extracted_line_items": 0,
  "live_seeding_active": false,
  "live_seeding_interval_seconds": 0
}
```

**What to point out:**
- The stats cache was computed from all 10,324 rows at startup
- `live_seeding_active: false` means data is static until a seed scenario is triggered

---

## Total: ~40 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Steps 1–2 — Quiet responses | Judgment layer stays silent on normal results | Engineering depth — selective anomaly voice |
| Step 3 — Stats cache | Live row counts, seeding state visible via API | Engineering depth |
