# FreightMind — Demo Script

Two-minute walkthrough covering the full end-to-end chain: analytics → extraction → verification → analytics-over-verification.

---

## Setup (before demo)

```bash
# Terminal 1 — backend
cd backend && uv run uvicorn app.main:app --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev

# Generate sample PDFs (one-time)
python scripts/create_sample_invoices.py
```

Open `http://localhost:3000` in browser.

---

## Part 1 Demo (~1 minute)

### Analytics Flow

1. Open the **Analytics** tab
2. Ask: *"Which country had the highest freight cost last month?"*
   - ✅ Shows: grounded text answer, SQL used, result table, bar chart
3. Follow-up: *"Break that down by shipment mode"*
   - ✅ Shows refined result (demonstrates follow-up interaction)
4. Ask something the data can't answer: *"What is the CEO's name?"*
   - ✅ Shows: "I cannot answer this from the dataset" — no hallucination

### Extraction Flow

5. Switch to the **Documents** tab
6. Upload `demo/sample_invoice_approved.pdf`
   - ✅ Shows: extracted fields with confidence badges (HIGH/MEDIUM/LOW)
   - ✅ Shows: `low_confidence_fields` list if any
7. Confirm the extraction
8. Switch back to **Analytics** and ask: *"Show me all extracted invoices"*
   - ✅ Shows: data from `extracted_documents` table — Part 1 linkage live

---

## Part 2 Demo (~1 minute)

### Verification Flow — Amendment Scenario

9. Navigate to `http://localhost:3000/verification`
10. Select customer: **GlobalTech Industries (DEMO_CUSTOMER_001)**
11. Upload `demo/sample_invoice_amendment.pdf`
12. ✅ **State 1 — Incoming:** Spinner shows while agent processes
13. ✅ **State 2 — Verification Result:**
    - Red banner: "Amendment Required — discrepancies found"
    - Field table shows: `hs_code` → **Mismatch**, `incoterms` → **Mismatch**
    - Other fields → **Match** with green badges
14. Click the `hs_code` mismatch row:
    - ✅ **State 3 — Discrepancy Detail:**
      - Extracted: `8471.40.00`
      - Expected: `8471.30.00`
      - Rule: "Laptop computers HS code per customs agreement CA-2024-GT"
15. Scroll to draft reply:
    - ✅ **State 4 — Draft Reply:** LLM-generated amendment request email listing both discrepancies
    - Edit the email (demonstrate CG control)
    - Click "Send to SU" → ✅ Sent badge appears

### Verification Flow — Approved Scenario

16. Click "← New document"
17. Upload `demo/sample_invoice_approved.pdf`
18. ✅ **Verification Result:** Green banner "Approved — all fields verified"
19. All fields show **Match** with green badges
20. Draft reply is an approval confirmation

### Failure Scenario

21. Submit with an empty or corrupted file (or a .txt file)
    - ✅ Returns `status: failed` with error message — no crash, CG notified

### Analytics Over Verification History

22. Navigate back to `http://localhost:3000` → **Analytics** tab
23. Ask: *"Which verification fields have mismatched most often?"*
    - ✅ Analytics agent queries `verification_fields` table
    - ✅ Returns: field names, mismatch counts — Part 1 analytics over Part 2 data

---

## Key Points to Highlight

| What evaluators look for | Where to show it |
|---|---|
| No hallucination | Ask an unanswerable analytics question |
| Confidence transparency | Extraction view — confidence badges per field |
| No silent approvals | Low-confidence field → `uncertain` even if value matches |
| Fail loud | Submit corrupted file — graceful error, record stored |
| Agent never sends | Draft reply requires CG to click Send |
| Separation of concerns | Comparator is separate from extractor — independently testable |
| Shared data store | Analytics queries verification history (step 23) |
| Rules in config | Show `backend/config/customer_rules/DEMO_CUSTOMER_001.json` |
