# FreightMind — Demo 07: Vision Extraction — Edge Cases (≤ 2 min)

NOT_FOUND badges on missing fields, LOW confidence on ambiguous values, and non-Latin scripts in address fields — the system surfaces uncertainty rather than hallucinating.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**, Documents tab active.

---

## Step 1 — Missing field: NOT_FOUND badge (~25 s)

Upload:

```
backend/data/demo_invoices/demo-06-no-insurance-line.png
```

**Expected extraction result:** `total_insurance_usd` shows a **NOT_FOUND** badge. All other present fields show HIGH.

**What to point out:**
- The invoice genuinely has no insurance line — the model did not hallucinate a value
- `NOT_FOUND` is an explicit signal, not a silent NULL — the user knows why it's missing
- Click **Discard** (do not confirm)

---

## Step 2 — Ambiguous field: LOW confidence badge (~25 s)

Upload:

```
backend/data/demo_invoices/demo-04-low-confidence-paymentterms.png
```

**Expected extraction result:** `payment_terms` shows a **LOW** (yellow) badge. Financial fields show HIGH.

**What to point out:**
- The model flagged its own uncertainty on a partially obscured field
- The user is prompted to review before confirming — uncertainty is surfaced, not silently accepted
- Click **Discard**

---

## Step 3 — Non-Latin script: Chinese consignee (~25 s)

Upload:

```
backend/data/demo_invoices/demo-07-air-usa-china.png
```

**Expected extraction result:** `consignee_name` contains Chinese characters (北京医疗物资有限公司 or transliteration). `destination_country: China`, `shipment_mode: Air` show HIGH.

**What to point out:**
- The vision model reads non-Latin script in the consignee block
- A rotated APPROVED stamp overlaps part of the address — the model handled the occlusion
- Click **Discard**

---

## Step 4 — Correction marks: Cyrillic shipper (~20 s)

Upload:

```
backend/data/demo_invoices/demo-09-truck-russia-kazakhstan.pdf
```

**Expected extraction result:** `shipper_name` in Cyrillic (ООО «Транснефть» or similar). `weight_kg` shows MEDIUM — the invoice has a strikethrough correction mark on that field.

**What to point out:**
- The model must decide between the struck-through original and the handwritten correction
- MEDIUM confidence signals the ambiguity correctly — this field needs human review
- Click **Discard**

---

## Total: ~95 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — NOT_FOUND | Missing field explicitly flagged, not NULL | Failure handling — cannot extract with confidence |
| Step 2 — LOW confidence | Model self-reports uncertainty | Failure handling — flag uncertain extractions |
| Step 3 — Non-Latin script | CJK + stamp occlusion handling | Behaviour B |
| Step 4 — Correction marks | Cyrillic + strikethrough ambiguity | Behaviour B |
