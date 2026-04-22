# FreightMind — Manual Test Checklist

**Assignment:** GoComet DAW — AI Solutions Engineer (Parts 1 & 2)  
**Customer:** DEMO_CUSTOMER_001 — GlobalTech Industries  
**Rules in effect:** HS code `8471.30.00` (exact) · Incoterms `CIF` (exact) · Consignee contains `GlobalTech Industries Ltd.` · Port of loading contains `Shanghai` · Port of discharge contains `Rotterdam` · Shipment mode `Ocean` (exact) · Origin country contains `China`

---

## 0. Setup

| # | Step | Expected | Pass |
|---|------|----------|------|
| 0.1 | Copy `.env.example` → `.env` and set `OPENROUTER_API_KEY` | `.env` file present | ☐ |
| 0.2 | `docker compose up --build` from repo root | Both services start, no crash | ☐ |
| 0.3 | `GET http://localhost:8000/api/health` | `{"status": "ok"}` | ☐ |
| 0.4 | Open `http://localhost:3000` | Page loads with nav bar ("Analytics & Docs" / "Verification") | ☐ |

---

## 1. Part 1 — Analytics Agent (NL → SQL)

### 1.1 Basic queries (shipments table)

| # | Question to type | Expected behaviour | Pass |
|---|------------------|--------------------|------|
| 1.1a | `How many shipments are in the dataset?` | Single number result, SQL shown, no error | ☐ |
| 1.1b | `What are the top 5 vendors by total freight cost?` | Table with 5 rows, `vendor` + `freight_cost_usd` columns | ☐ |
| 1.1c | `Show shipments by country in 2015` | `strftime` used in SQL (not `EXTRACT`), results grouped by country | ☐ |
| 1.1d | `What is the average pack price by shipment mode?` | Grouped result, `AVG` in SQL | ☐ |

### 1.2 Follow-up / context continuity

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 1.2a | After 1.1b, ask `Which of those vendors is in Nigeria?` | Query narrows to Nigeria, references correct vendor column, not previous SQL structure | ☐ |

### 1.3 Cross-table: verification history (Part 2 tables queryable via Part 1)

| # | Question | Expected | Pass |
|---|----------|----------|------|
| 1.3a | `How many verifications have been done so far?` | Count from `verification_results` table | ☐ |
| 1.3b | `Which fields fail most often in verifications?` | Uses `verification_fields`, groups by `name`, counts `mismatch` or `uncertain` | ☐ |
| 1.3c | `What is the overall approval rate?` | Percentage of `approved` vs total from `verification_results` | ☐ |

### 1.4 Safety guard

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 1.4a | Type `Delete all shipments` | Rejected — 422 with `unsafe_sql` error, nothing deleted | ☐ |

---

## 2. Part 1 — Vision Document Extraction

### 2.1 Upload and review

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 2.1a | Switch to "Documents" tab, upload `demo/sample_invoice_approved.pdf` | Extraction starts, review table renders with fields and confidence badges | ☐ |
| 2.1b | Verify new trade fields are extracted: `hs_code`, `incoterms`, `port_of_loading`, `port_of_discharge`, `description_of_goods` | All 5 fields appear in review table | ☐ |
| 2.1c | Check at least one field shows a HIGH confidence badge | Badge present | ☐ |
| 2.1d | Click "Confirm" | `confirmed_by_user = 1` set; success message shown | ☐ |

### 2.2 Analytics query against confirmed invoice

| # | Question | Expected | Pass |
|---|----------|----------|------|
| 2.2a | `What is the freight cost in my confirmed invoice?` | Uses `extracted_documents` with `confirmed_by_user = 1`, returns `total_freight_cost_usd` | ☐ |
| 2.2b | `Compare my confirmed invoice freight cost against the dataset average` | UNION ALL result — one row for invoice, one row for dataset average | ☐ |

---

## 3. Part 2 — Verification: Happy Path (Approved)

**Use file:** `demo/sample_invoice_approved.pdf`

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 3.1 | Navigate to `/verification` | Upload form loads (idle state) | ☐ |
| 3.2 | Select `demo/sample_invoice_approved.pdf`, customer defaults to `DEMO_CUSTOMER_001`, click Submit | Spinner/incoming state shows | ☐ |
| 3.3 | Pipeline completes | Result state loads; no crash | ☐ |
| 3.4 | Status banner shows **Approved** (green) | Green banner | ☐ |
| 3.5 | Field table shows all 7 ruled fields with **match** status | `hs_code`, `incoterms`, `consignee_name`, `port_of_loading`, `port_of_discharge`, `shipment_mode`, `origin_country` — all green | ☐ |
| 3.6 | Draft reply textarea is populated with an approval confirmation email | Draft contains positive language, no amendment requests | ☐ |
| 3.7 | Edit the draft and click "Send to SU" | UI shows sent confirmation; agent never sends autonomously | ☐ |

---

## 4. Part 2 — Verification: Amendment Required

**Use file:** `demo/sample_invoice_amendment.pdf`  
*(HS code is `8471.40.00` instead of `8471.30.00`; Incoterms is `FOB` instead of `CIF`)*

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 4.1 | Upload `demo/sample_invoice_amendment.pdf`, customer `DEMO_CUSTOMER_001` | Spinner shows | ☐ |
| 4.2 | Status banner shows **Amendment Required** (red/orange) | Correct banner colour | ☐ |
| 4.3 | Field table shows `hs_code` as **mismatch** — extracted `8471.40.00`, expected `8471.30.00` | Mismatch row with both values visible | ☐ |
| 4.4 | Field table shows `incoterms` as **mismatch** — extracted `FOB`, expected `CIF` | Mismatch row | ☐ |
| 4.5 | All other 5 fields show **match** | Remaining fields green | ☐ |
| 4.6 | Draft reply lists the two specific discrepancies | Amendment email body names `hs_code` and `incoterms` | ☐ |
| 4.7 | Clicking a mismatch row expands the discrepancy detail (extracted vs expected + rule description) | Discrepancy panel shows rule violated (e.g. "Laptop computers HS code per customs agreement CA-2024-GT") | ☐ |

---

## 5. Part 2 — Failure Scenarios (5 required by spec)

### Failure 1: Obscured HS code → uncertain, not approved

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 5.1a | Upload any invoice where HS code is illegible or missing | `hs_code` field shows **uncertain** status with LOW/0.0 confidence | ☐ |
| 5.1b | Overall status is **Uncertain** or **Amendment Required**, NOT Approved | Status is not green | ☐ |

*Simulate by uploading a heavily-compressed or text-obscured PDF, or manually test by checking that `NOT_FOUND` confidence → 0.0 → uncertain in the comparator.*

### Failure 2: LLM returns unrecognised format → uncertain, raw value preserved

| # | What to verify | Expected | Pass |
|---|---------------|----------|------|
| 5.2 | If LLM outputs an unexpected structure, the extraction verifier coerces unknown confidence strings to LOW (0.3) → comparator marks field uncertain | Field is uncertain, not crashed | ☐ |

*Verify in code: `ExtractionVerifier.score_confidence()` maps unrecognised confidence strings to LOW — this handles the scenario defensively without a manual trigger.*

### Failure 3: Config missing for customer → failed result, CG notified

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 5.3a | In the customer_id field, enter `UNKNOWN_CUSTOMER_999` and submit any PDF | Response returns `overall_status: "failed"` | ☐ |
| 5.3b | Error message references the missing customer config, not a 500 | UI shows "No rule configuration found for customer 'UNKNOWN_CUSTOMER_999'" | ☐ |
| 5.3c | A failed record is stored — query `GET /api/verify/queue` | Record appears with `overall_status: failed` | ☐ |

### Failure 4: Empty or corrupted file → graceful error

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 5.4a | Upload a 0-byte file (e.g. `touch empty.pdf` and upload it) | `overall_status: failed`, error about missing content | ☐ |
| 5.4b | Upload a `.txt` file renamed to `.pdf` (wrong MIME) | Pipeline attempts extension sniffing, then if truly unsupported → `overall_status: failed` | ☐ |
| 5.4c | Upload a file over 10 MB | HTTP 413 returned before pipeline runs | ☐ |
| 5.4d | No partial result is stored for corrupted files | Queue does not show a partial extraction | ☐ |

### Failure 5: LLM API timeout / failure → retry once, then failed record

| # | What to verify | Expected | Pass |
|---|---------------|----------|------|
| 5.5 | `ModelClient` retries up to 4 times on LLM failure; if all retries fail, `run_verification` catches the exception and calls `_store_failed()` | No uncaught exception, no crash; CG sees `overall_status: failed` with error detail | ☐ |

*Verify in code: `pipeline.py` lines 96–105 catch `Exception` from `executor.extract()` after retries and call `_store_failed()`.*

---

## 6. Part 2 — Verification Queue / History

| # | Action | Expected | Pass |
|---|--------|----------|------|
| 6.1 | `GET http://localhost:8000/api/verify/queue` | JSON list of past verifications, newest first | ☐ |
| 6.2 | Each entry includes `overall_status`, `shipment_id`, `received_at`, `mismatch_count`, `field_count` | All fields present | ☐ |
| 6.3 | `GET http://localhost:8000/api/verify/result/{id}` with an ID from the queue | Full field-by-field result returned | ☐ |
| 6.4 | After running Tests 3 and 4 above, analytics question `How many verifications have been done?` returns a count ≥ 2 | Cross-table query works | ☐ |

---

## 7. Architecture Verification (Spec Compliance)

| # | Requirement | How to verify | Pass |
|---|-------------|---------------|------|
| 7.1 | Comparison layer is separate from extraction layer | `backend/app/agents/verification/comparator.py` exists as an independent module | ☐ |
| 7.2 | Customer rules in config file only — no code changes to swap customer | Change `customer_id` field in the UI; `backend/config/customer_rules/` holds one JSON per customer | ☐ |
| 7.3 | Confidence thresholds configurable per customer (not hardcoded) | `DEMO_CUSTOMER_001.json` has `confidence_thresholds.uncertain_below = 0.6`; changing this file changes behaviour | ☐ |
| 7.4 | All verification results in same DB as Part 1 shipments | `backend/freightmind.db` contains `verification_results` and `verification_fields` tables | ☐ |
| 7.5 | Agent never sends autonomously | "Send to SU" button in UI is the only send action; backend has no email/webhook send code | ☐ |
| 7.6 | Draft reply always produced | Even on `overall_status: failed`, `draft_reply` field is populated with a CG-facing message | ☐ |
| 7.7 | Uncertain fields clearly marked — CG cannot mistake uncertain for confirmed | UI shows distinct badge/colour for `uncertain` vs `match` | ☐ |

---

## 8. Bug Fix Verification

| # | Fix | How to verify | Pass |
|---|-----|---------------|------|
| 8.1 | UNION ALL parentheses fix (SQLite crash) | Ask `Compare freight costs for air vs ocean shipments` — query runs without `sqlite3.OperationalError` | ☐ |
| 8.2 | `extracted_documents` wrong column names fixed | Ask `What is the freight cost in my confirmed invoice?` — no `no such column` error | ☐ |
| 8.3 | Dirty session fix in `_store_failed()` | Submit a document for `UNKNOWN_CUSTOMER_999` — returns `failed` status, not a 500 | ☐ |
| 8.4 | Config copy in Docker image | After `docker compose up --build`, submit to `/verify/submit` — no "Customer rules missing" log error | ☐ |

---

## Quick curl Reference

```bash
# Health
curl http://localhost:8000/api/health

# Analytics query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many shipments are in the dataset?"}'

# Verify — approved invoice
curl -X POST http://localhost:8000/api/verify/submit \
  -F "file=@demo/sample_invoice_approved.pdf;type=application/pdf" \
  -F "customer_id=DEMO_CUSTOMER_001"

# Verify — amendment invoice
curl -X POST http://localhost:8000/api/verify/submit \
  -F "file=@demo/sample_invoice_amendment.pdf;type=application/pdf" \
  -F "customer_id=DEMO_CUSTOMER_001"

# Missing customer (failure scenario 3)
curl -X POST http://localhost:8000/api/verify/submit \
  -F "file=@demo/sample_invoice_approved.pdf;type=application/pdf" \
  -F "customer_id=UNKNOWN_CUSTOMER_999"

# Empty file (failure scenario 4a — create first)
touch /tmp/empty.pdf
curl -X POST http://localhost:8000/api/verify/submit \
  -F "file=@/tmp/empty.pdf;type=application/pdf" \
  -F "customer_id=DEMO_CUSTOMER_001"

# Verification queue
curl http://localhost:8000/api/verify/queue

# Single result (replace 1 with actual ID)
curl http://localhost:8000/api/verify/result/1
```

---

## Notes

- **Rebuild required** after this session's Dockerfile fix: `docker compose up --build` (the `config/` directory is now copied into the image — this fixes the "Customer rules missing" error seen in Docker logs).
- Sample PDFs are in `demo/` — use these for Tests 3 and 4.
- Failure scenarios 1 and 2 are defensive code paths verified by reading the code rather than a reproducible UI trigger; the curl tests cover the three that are directly triggerable.
