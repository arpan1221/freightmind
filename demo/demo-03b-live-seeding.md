# FreightMind — Demo 03b: Live Seeding (Living Dataset)

The background seeder drips synthetic rows into the database at a fixed interval. Row counts tick up in the UI, stats refresh automatically, and the anomaly layer engages naturally as the data shifts — no manual curl commands needed.

---

## 0. Prerequisites

Set `LIVE_SEEDING_INTERVAL_SECONDS=30` in `.env` before starting:

```bash
echo "LIVE_SEEDING_INTERVAL_SECONDS=30" >> .env
docker compose up --build
```

Browser open at **http://localhost:3000**.

> **Note:** Demos 03–05 assume `LIVE_SEEDING_INTERVAL_SECONDS=0`. This demo is a separate mode — do not mix them in the same session.

---

## Step 1 — Observe the live counter (~30 s)

Watch the **Shipments** card in the dataset status grid at the top of the page.

**What to point out:**
- The green dot on the Shipments card **pulses** (animate-ping) — live seeding is active
- Every 30 seconds, 42 new rows are inserted from the next scenario in rotation
- The counter ticks up and the card briefly flashes green when new rows land
- No page refresh needed — the frontend polls `/api/stats/live` every 5 seconds

---

## Step 2 — Ask a question before the first seed cycle (~20 s)

In the **Analytics** tab, type:

```
What are the top 5 destination countries by number of Air shipments?
```

**Expected output:** Nigeria at ~547. Clean answer, no anomaly note (baseline is intact at startup).

---

## Step 3 — Wait for a seed cycle, then ask the same question (~30 s)

Wait until the Shipments counter increments (up to 30 seconds). Then type:

```
What are the top 5 destination countries by number of Air shipments?
```

**Expected output:** Nigeria count has increased. If it crosses the IQR fence (~565), the answer now contains an anomaly note.

**What to point out:**
- The answer changed without any manual intervention
- The system detected the change, updated its statistical model, and reported the anomaly
- The data felt live — because it is

---

## Step 4 — Check what was seeded (~15 s)

Type:

```
Show me the 5 most recently delivered shipments
```

**Expected output:** Rows with `delivered_to_client_date` in 2025–2026 — the synthetic rows are distinguishable from SCMS 2006–2015 data by their delivery dates.

**What to point out:**
- Seeded rows are real SQLite rows, not mocked — fully queryable
- The date range difference is visible in the SQL result
- SQL disclosure shows `ORDER BY delivered_to_client_date DESC LIMIT 5`

---

## Step 5 — Ocean cost spike emerges naturally (~varies)

After 2 seed cycles (60 s), the rotation reaches `ocean_cost_spike`. Type:

```
What is the average freight cost for Ocean shipments?
```

**Expected output:** If the new average crosses the Ocean IQR fence (~$28,875), the answer includes a freight cost anomaly note.

**What to point out:**
- No manual seeding was needed — the insight surfaced on its own
- Different anomaly type (freight cost, not volume) fires on a different dimension
- This is the system operating as an analytics agent that watches its own data

---

## Total: ~95 seconds (plus wait time for seed cycles)

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Counter ticks | Live data visible in UI | Engineering depth |
| Step 2 — Baseline query | System quiet before first cycle | Engineering depth |
| Step 3 — Anomaly fires naturally | No manual trigger needed | Engineering depth |
| Step 4 — Recent rows | Synthetic rows are fully queryable | Behaviour A |
| Step 5 — Second anomaly type | Different dimension, different insight | Engineering depth |

---

## Turning off live seeding

Set `LIVE_SEEDING_INTERVAL_SECONDS=0` in `.env` and rebuild. The pulsing dot reverts to a static green dot, seeding stops, and Demos 03–05 work as documented.
