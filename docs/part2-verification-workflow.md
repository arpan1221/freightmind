# Part 2 — SU → CG Verification Workflow

## Context

Today, Cargo Control Group (CG) spends hours per shipment manually checking every field in every document sent by Shipping Units (SU) against customer-specific requirements. Two to four amendment cycles per shipment is normal.

FreightMind Part 2 automates the mechanical part: extraction, comparison, flagging, and draft reply generation.

---

## The Three Actors

| Actor | Role | Constraint |
|---|---|---|
| SU | Sends trade documents (Commercial Invoice, B/L, Packing List, CoO) | Job feels done once email is out |
| CG | Validates every field against customer requirements | Throughput is the bottleneck |
| Customer | Receives final document set | Wrong HS code or mismatched consignee = customs delay, contract penalty |

---

## Pipeline: 5 Steps

### Step 1 — Trigger

SU document arrives. In production this would be an email webhook (e.g. AWS SES → Lambda → API call). In the demo, it's a file upload to `POST /api/verify/submit`.

The trigger passes: file bytes, content type, filename, customer_id.

### Step 2 — Extract

Reuses the Part 1 Vision Document Agent (ExtractionPlanner → ExtractionExecutor → ExtractionVerifier).

Fields extracted with per-field confidence (HIGH/MEDIUM/LOW/NOT_FOUND):
- `invoice_number`, `invoice_date`, `shipper_name`, `consignee_name`
- `origin_country`, `destination_country`, `shipment_mode`, `carrier_vendor`
- `total_weight_kg`, `total_freight_cost_usd`, `total_insurance_usd`, `payment_terms`, `delivery_date`
- `hs_code` *(Part 2)* — Harmonized System / HTS code
- `port_of_loading` *(Part 2)* — origin port
- `port_of_discharge` *(Part 2)* — destination port
- `incoterms` *(Part 2)* — e.g. CIF, FOB, EXW
- `description_of_goods` *(Part 2)* — primary goods description

### Step 3 — Compare

`DocumentComparator` (completely separate module from extraction) loads the customer rules config and compares each extracted value against the expected value.

**Comparison logic:**
```python
if confidence < uncertain_threshold:         # default 0.6
    status = "uncertain"                     # even if value matches
elif extracted value is None:
    status = "uncertain"
elif no rule defined for this field:
    status = "no_rule"                       # not auto-approved
elif value matches expected (match_type):
    status = "match"
else:
    status = "mismatch"
```

`match_type: "exact"` → case-insensitive equality
`match_type: "contains"` → case-insensitive substring (either direction)

### Step 4 — Flag

`determine_overall_status()` derives the shipment-level verdict:

| Fields present | Overall status |
|---|---|
| Any `mismatch` | `amendment_required` |
| Any `uncertain` (no mismatches) | `uncertain` |
| All `match` or `no_rule` | `approved` |
| Pipeline failure | `failed` |

### Step 5 — Draft

`VerificationDrafter` calls the analytics LLM model to generate a professional email:
- **Amendment required / uncertain:** structured discrepancy list with field name, extracted value, expected value, rule violated
- **Approved:** concise approval confirmation

The draft is always editable by CG before sending. The agent never sends autonomously.

Template fallback ensures a draft is always produced even if the LLM call fails.

---

## Customer Rules Config

Located at: `backend/config/customer_rules/<customer_id>.json`

Swapping customers means swapping the config file. No agent code changes.

```json
{
  "customer_id": "DEMO_CUSTOMER_001",
  "customer_name": "GlobalTech Industries",
  "rules": {
    "hs_code": {
      "expected": "8471.30.00",
      "match_type": "exact",
      "description": "Laptop computers HS code per customs agreement CA-2024-GT"
    }
  },
  "confidence_thresholds": {
    "uncertain_below": 0.6
  }
}
```

---

## CG User Interface — 4 States

### State 1: Incoming
Shown while the pipeline runs. Displays a spinner with status messages:
- "Extracting fields with vision model…"
- "Comparing against customer rules…"
- "Generating draft reply…"

### State 2: Verification Result
Field-by-field table showing:
- Field name, extracted value, expected value
- Status badge (Match / Mismatch / Uncertain / No Rule)
- Confidence bar (colour-coded: green ≥80%, amber ≥50%, red <50%)

Summary row: X matched, X mismatched, X uncertain, X no rule.

### State 3: Discrepancy Detail
Clicking any `mismatch` or `uncertain` row expands to show:
- Extracted value (what the agent read)
- Expected value (what the rule requires)
- Rule description (the business reason)
- Confidence percentage with explanation if uncertain

### State 4: Draft Reply
Editable textarea pre-populated with the LLM-generated email. CG can modify, reset, or send. A "Sent" badge is displayed after CG confirms.

---

## Failure Scenarios (Assignment Spec)

All five are tested:

| Scenario | Expected | How Handled |
|---|---|---|
| HS code partially obscured | Uncertain + low confidence, not approved | Vision LLM returns MEDIUM/LOW → comparator marks `uncertain` |
| LLM returns unrecognised format | Status `uncertain`, raw value preserved | `score_confidence()` coerces to LOW → comparator marks `uncertain` |
| Customer config missing a rule for a field | Field marked `no_rule`, surfaced in UI | Comparator checks rule dict; absent = `no_rule` status |
| No attachment / corrupted document | Graceful error, CG notified, no partial result | `_store_failed()` called before any extraction — full record stored with `status: failed` |
| LLM API fails or times out | Retry once; failed record stored, CG notified | ModelClient retries internally; on persistent failure → `_store_failed()` |

---

## Part 1 Linkage

The `verification_fields` table is in the same SQLite DB as `shipments` and `extracted_documents`. The analytics agent can answer:

> "Which fields failed most often this week?"

```sql
SELECT name, COUNT(*) as fail_count
FROM verification_fields
WHERE status IN ('mismatch', 'uncertain')
  AND verification_id IN (
    SELECT id FROM verification_results
    WHERE received_at >= date('now', '-7 days')
  )
GROUP BY name
ORDER BY fail_count DESC
```

No changes to the analytics agent were required — it uses the same schema-aware SQL generation against the shared DB.

---

## Sample Documents

| File | Expected Result |
|---|---|
| `demo/sample_invoice_approved.pdf` | All fields match → `approved` |
| `demo/sample_invoice_amendment.pdf` | HS code: 8471.40.00 (expected 8471.30.00), Incoterms: FOB (expected CIF) → `amendment_required` |

Generated by: `python scripts/create_sample_invoices.py`
