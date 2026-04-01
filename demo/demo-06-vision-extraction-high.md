# FreightMind — Demo 06: Vision Extraction — High Confidence (≤ 2 min)

Upload a freight invoice, review vision-extracted fields with HIGH confidence badges, confirm to database, then query it analytically.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**.  
Invoice file: `backend/data/demo_invoices/demo-01-air-nigeria-linkage.pdf`

---

## Step 1 — Upload the invoice (~30 s)

Switch to the **Documents** tab. Drag `demo-01-air-nigeria-linkage.pdf` onto the upload zone.

**What to point out:**
- Loading indicator while the vision model processes page 1 of the PDF
- The extraction runs through the same Planner → Executor → Verifier pipeline as analytics

---

## Step 2 — Review the extraction table (~20 s)

**Expected extraction result:**

| Field | Value | Badge |
|-------|-------|-------|
| invoice_number | INV-2024-001 | HIGH |
| shipment_mode | Air | HIGH |
| destination_country | Nigeria | HIGH |
| weight_kg | 285.0 | HIGH |
| freight_cost_usd | 8,920.00 | HIGH |
| shipper_name | FreightBridge Ltd | HIGH |
| consignee_name | Lagos Medical Supplies | HIGH |

**What to point out:**
- GREEN badges (`HIGH`) on all clearly legible fields
- Each field scored independently — HIGH / MEDIUM / LOW / NOT_FOUND
- Click into a field to edit inline before confirming (demonstrates human-in-the-loop review)

---

## Step 3 — Confirm the extraction (~5 s)

Click **Confirm**. The extraction persists to `extracted_documents` and `extracted_line_items`.

**What to point out:**
- Documents tab badge increments to 1
- Data is now queryable via the analytics agent

---

## Step 4 — Query the confirmed invoice (~20 s)

Switch to the **Analytics** tab and type:

```
What shipment mode and freight cost were on my last confirmed invoice?
```

**Expected output:** *"Your confirmed invoice shows Air mode with a freight cost of $8,920.00."*

**What to point out:**
- The SQL queries `extracted_documents WHERE confirmed_by_user = 1`
- Analytics and extraction share the same SQLite store — no data pipeline between them

---

## Total: ~75 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Upload | Vision pipeline initiated | Behaviour B |
| Step 2 — Review | Confidence badges, inline edit | Behaviour B |
| Step 3 — Confirm | Extraction persisted to DB | Behaviour B |
| Step 4 — Query | Confirmed data immediately queryable | Behaviour A + B |
