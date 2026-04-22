# PRD — Part 2: Agentic Document Verification (SU → CG Workflow)

**Status:** Implemented  
**Author:** Arpan (AI Solutions Engineer candidate)  
**Date:** 2026-04-09  
**Assignment:** GoComet DAW — AI Solutions Engineer  

---

## 1. Problem Statement

Cargo Control Group (CG) spends hours per shipment manually checking every field in trade documents sent by Shipping Units (SU) against customer-specific requirements. Two to four amendment cycles per shipment is the norm. Each cycle adds hours of delay.

**What breaks down technically:**
- No structured format — docs arrive as free-form PDFs
- Customer rules are undocumented, per-customer, in people's heads
- No programmatic comparison layer
- No storage or audit trail for past verifications
- No way to query: which fields fail most often?
- CG throughput is the bottleneck for shipment velocity

---

## 2. Goal

Automate the mechanical validation work: extraction, comparison, flagging, and draft generation should not require a human. The three-party structure (SU → CG → Customer) stays intact. CG remains in control of the final send.

---

## 3. Users

| User | Role | Success Metric |
|---|---|---|
| CG Operator | Receives docs, validates, sends reply | Verification time from minutes to seconds |
| SU | Sends trade documents | Clear, specific amendment requests on first response |
| Customer | Receives final document set | Zero customs delays due to wrong field values |

---

## 4. Scope

### In Scope
- Document trigger mechanism (simulated inbox via API endpoint)
- Field extraction reusing Part 1 Vision Document Agent
- Customer rules config system (JSON per customer, no code changes to swap)
- Field-by-field comparison with confidence thresholds (configurable)
- Structured discrepancy output with match/mismatch/uncertain/no_rule status
- LLM-generated draft amendment request or approval email
- CG verification UI with 4 states driven by real agent output
- All verification results persisted to shared SQLite DB
- Part 1 analytics layer queryable over verification history

### Out of Scope
- Actual email sending (CG always controls the send)
- Multi-document batch processing
- Real-time email/webhook integration (folder watcher or webhook can call the same endpoint)
- Historical customer rule versioning

---

## 5. Functional Requirements

### FR-1: Trigger
The system must activate when an SU document arrives. A folder watcher or CLI/API trigger is acceptable. Email plumbing is not required.

### FR-2: Extraction
Reuse Part 1 Vision Document Agent. Extract trade document fields including: consignee name, HS code, port of loading/discharge, Incoterms, description of goods, gross weight, invoice number. Surface confidence per field.

### FR-3: Comparison
Compare each extracted field against a customer rule set stored in a config file (JSON/YAML). Produce: `match`, `mismatch`, or `uncertain` for every field. Customer rules must be swappable via config — no agent code changes.

### FR-4: Flagging
Output a structured verification result per field: name, extracted value, expected value, match status, confidence score. Low-confidence extractions must be flagged as `uncertain` even if the value appears to match. No silent approvals.

### FR-5: Draft Generation
Generate a draft amendment request (if issues found) or approval confirmation (if all clear). CG must be able to edit before sending. Agent never sends autonomously.

### FR-6: Persistence
All verification results must be stored in the same data store as Part 1. Schema must be queryable by the Part 1 analytics layer.

### FR-7: UI
A working UI module that renders in a browser with four states driven by real agent output:
1. Incoming — processing state
2. Verification result — field-by-field with confidence visualization
3. Discrepancy detail — expandable per flagged field
4. Draft reply — editable by CG before sending

---

## 6. Non-Functional Requirements

### NFR-1: Failure Handling (must pass all 5 scenarios)
| Scenario | Required Behaviour |
|---|---|
| HS code obscured in PDF | Uncertain + low confidence, not approved |
| LLM returns unrecognised format | Uncertain, raw value preserved, not corrected |
| Config missing a rule for a field | `no_rule` status, not auto-approved, surfaced in UI |
| No attachment / corrupted file | Graceful error, CG notified, no partial result stored |
| LLM API fails / times out | Retry once; store failed record, surface to CG, no crash |

### NFR-2: Architecture
- Comparison layer must be a separate module from extraction layer (independently testable)
- Customer rules in config file only (not hardcoded in agent logic)
- Confidence thresholds configurable per customer (not magic numbers in code)
- Schema must match the minimum spec (shipment_id, received_at, customer_id, fields array, overall_status, draft_reply)

### NFR-3: Transparency
- Uncertain fields clearly marked — CG must never mistake an uncertain extraction for confirmed
- Confidence scores visually distinct (high/medium/low)
- Discrepancy detail shows extracted vs expected + rule violated

---

## 7. Data Schema (Minimum — from Assignment Spec)

```json
{
  "shipment_id": "string",
  "received_at": "ISO timestamp",
  "customer_id": "string",
  "fields": [
    {
      "name": "string",
      "extracted": "string",
      "expected": "string",
      "status": "match | mismatch | uncertain",
      "confidence": "float 0.0–1.0"
    }
  ],
  "overall_status": "approved | amendment_required | uncertain",
  "draft_reply": "string"
}
```

**Extensions implemented:** `customer_name`, `error_message` (for failed status), `rule_description` (per field).

---

## 8. Acceptance Criteria

- [ ] Full pipeline runs end-to-end from trigger to UI display
- [ ] All 5 failure scenarios handled without crash or silent approval
- [ ] Comparison layer is a separate module from extraction layer
- [ ] Customer rules live in JSON config; swapping customer_id loads different rules
- [ ] Confidence thresholds configurable in rules config (not hardcoded)
- [ ] Verification results queryable via Part 1 analytics agent
- [ ] UI shows all 4 states driven by real agent output (not dummy data)
- [ ] Draft reply is editable by CG before sending
- [ ] Agent never sends autonomously

---

## 9. Implementation Notes

### Trigger Mechanism
`POST /api/verify/submit` — multipart file upload + customer_id form field. Simulates SU email arriving. A folder watcher, AWS SES webhook, or any other integration calls this endpoint.

### Confidence Conversion
Extraction agent uses `HIGH/MEDIUM/LOW/NOT_FOUND` strings. Comparator converts to floats: `HIGH=0.9, MEDIUM=0.6, LOW=0.3, NOT_FOUND=0.0`. Configurable `uncertain_below` threshold (default 0.6).

### No Silent Approvals
The comparator checks confidence before checking value match. A field with `confidence < uncertain_threshold` is always `uncertain`, even if the extracted value equals the expected value.

### Part 1 Linkage
`verification_fields` table is in the same SQLite DB as `shipments` and `extracted_documents`. No changes to the analytics agent — it generates SQL against the shared schema automatically.

---

## 10. Stories (Implemented)

| ID | Story | Status |
|---|---|---|
| P2-1 | Extend extracted_documents schema with 5 trade fields | ✅ Done |
| P2-2 | Extend extraction prompt to extract new trade fields | ✅ Done |
| P2-3 | Create verification_results + verification_fields DB tables | ✅ Done |
| P2-4 | Build DocumentComparator (separate module, rules from config) | ✅ Done |
| P2-5 | Build VerificationDrafter (LLM draft + template fallback) | ✅ Done |
| P2-6 | Build verification pipeline (Trigger→Extract→Compare→Flag→Draft) | ✅ Done |
| P2-7 | Handle all 5 failure scenarios in pipeline | ✅ Done |
| P2-8 | Create /api/verify/submit, /result, /queue endpoints | ✅ Done |
| P2-9 | Build /verification frontend route with 4 states | ✅ Done |
| P2-10 | Create DEMO_CUSTOMER_001 rules config | ✅ Done |
| P2-11 | Generate synthetic sample invoices (approved + amendment) | ✅ Done |
| P2-12 | Add navigation link from main app to /verification | ✅ Done |
