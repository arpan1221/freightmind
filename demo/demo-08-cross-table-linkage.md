# FreightMind — Demo 08: Cross-Table Linkage (≤ 2 min)

Analytics queries that JOIN confirmed invoices against 10,324 historical SCMS shipments — the SQL disclosure proves both tables are referenced.

---

## 0. Prerequisites

Stack running, browser open at **http://localhost:3000**.  
Complete **Demo 06** first — at least one confirmed invoice must exist in the database.

---

## Step 1 — Confirm baseline (~10 s)

In the **Analytics** tab, type:

```
How many confirmed invoices do I have?
```

**Expected output:** *"You have 1 confirmed invoice."*

**What to point out:**
- SQL queries `extracted_documents WHERE confirmed_by_user = 1`
- Confirms the extraction data is live and queryable before the linkage demo

---

## Step 2 — Core linkage query (~25 s)

Type:

```
Compare the freight cost from my confirmed invoice against the average freight cost for Air shipments to Nigeria in the dataset
```

**Expected output:**

| Source | Freight Cost USD |
|--------|-----------------|
| Confirmed invoice | 8,920.00 |
| Dataset average — Air / Nigeria | ~17,662 |

**What to point out:**
- Expand **SQL ▶** — the query references **both** `shipments` and `extracted_documents`
- The SCMS average is computed from 547 historical Air shipments to Nigeria
- This is the A → B linkage: the user's document is analytically comparable to historical data

---

## Step 3 — Insurance comparison (~20 s)

Type:

```
How does the insurance cost on my confirmed invoice compare to the dataset average for Air shipments?
```

**Expected output:** Two-row result — confirmed invoice insurance vs `AVG(shipments.line_item_insurance_usd)` for Air mode.

**What to point out:**
- SQL disclosure shows a UNION ALL or subquery pattern crossing both tables
- The answer explicitly labels which number came from where

---

## Step 4 — Multi-invoice follow-up (~20 s)

Click the suggested follow-up or type:

```
Which confirmed invoices have a freight cost above the dataset average for their shipment mode?
```

**Expected output:** Lists confirmed invoices where the freight cost exceeds the mode average from `shipments`.

**What to point out:**
- The SQL joins `extracted_documents` freight cost against a subquery computing mode averages from `shipments`
- Follow-up interaction refines the prior result using context from the previous query

---

## Total: ~75 seconds

| Beat | Demo purpose | Assignment criterion |
|---|---|---|
| Step 1 — Baseline count | Confirmed extraction visible to analytics | Behaviour B → A |
| Step 2 — Core linkage | SQL references both tables | Behaviour C |
| Step 3 — Insurance comparison | Second cross-table metric | Behaviour C |
| Step 4 — Follow-up | Contextual refinement across tables | Behaviour A follow-up |
