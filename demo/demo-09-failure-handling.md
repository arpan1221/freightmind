# FreightMind — Demo 09: Failure Handling & Trust (≤ 2 min)

The Verifier rejects unsafe SQL, the intent classifier stops hallucination, and the extraction pipeline surfaces uncertainty — all without crashing.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**. Reset chat history with the **Clear** button.

---

## Step 1 — Out-of-scope question (~15 s)

In the **Analytics** tab, type:

```
What is the carbon footprint of our shipments?
```

**Expected output:** The system responds that this cannot be answered from the available data — it does not hallucinate an answer.

**What to point out:**
- The intent classifier stopped before generating SQL — no query was even attempted
- The response tells the user what data IS available
- No error toast — this is a graceful, intentional refusal

---

## Step 2 — Unsafe SQL rejection (~15 s)

Type:

```
Delete all shipments where the country is Nigeria
```

**Expected output:** Error toast — *"The generated query was not allowed. Only read-only SELECT queries are permitted."*

**What to point out:**
- The Verifier intercepted the DELETE before it reached the database
- No data was modified — this is a hard architectural guard, not a soft warning
- The rejected SQL is shown in the disclosure for full transparency

---

## Step 3 — Low confidence extraction (~25 s)

Switch to the **Documents** tab and upload:

```
backend/data/demo_invoices/demo-04-low-confidence-paymentterms.png
```

**Expected extraction result:** `payment_terms` shows a LOW (yellow) badge.

**What to point out:**
- The model self-reported uncertainty — it did not silently accept an ambiguous value
- The user must review and decide before data is persisted
- Click **Discard**

---

## Step 4 — Empty-state graceful response (~15 s)

Ensure no documents are confirmed. Switch to **Analytics** and type:

```
List all my confirmed invoices and their freight costs
```

**Expected output:** *"There are no confirmed uploaded invoices yet. Open the Documents tab, upload a freight document, review it, and click Confirm."*

**What to point out:**
- No SQL error, no hallucinated result, no crash
- The system guides the user to the next action
- Analytics and extraction share the same store — the empty-state check is a live DB query

---

## Total: ~70 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Out of scope | Intent classifier prevents hallucination | Failure handling — must say so clearly |
| Step 2 — Unsafe SQL | Verifier rejects write operations | Failure handling — system must not crash |
| Step 3 — Low confidence | Model self-reports uncertainty | Failure handling — flag uncertain extractions |
| Step 4 — Empty state | Graceful no-data response | Failure handling — does not crash or hallucinate |
