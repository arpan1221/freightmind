# FreightMind — Data Models

All data lives in a single SQLite file: `backend/freightmind.db`.

The shared data store is intentional — the analytics agent (Part 1) can query verification history (Part 2) using the same natural language interface.

---

## Tables

### `shipments`

Source: SCMS_shipment_sample.csv, loaded at startup. ~10,000+ rows.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Not autoincrement — from CSV |
| project_code | TEXT | |
| country | TEXT | Indexed |
| shipment_mode | TEXT | Air / Ocean / Truck / Air Charter. Indexed |
| vendor | TEXT | Indexed |
| product_group | TEXT | Indexed |
| line_item_value | FLOAT | |
| weight_kg | FLOAT | |
| freight_cost_usd | FLOAT | |
| scheduled_delivery_date | TEXT | Indexed |
| ... | ... | 42 total columns — see DATASET_SCHEMA.md |

---

### `extracted_documents`

One row per uploaded trade document. Populated by the Vision Document Agent.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| source_filename | TEXT | Original upload filename |
| invoice_number | TEXT | |
| invoice_date | TEXT | As shown in document |
| shipper_name | TEXT | |
| consignee_name | TEXT | |
| origin_country | TEXT | Indexed |
| destination_country | TEXT | Indexed |
| shipment_mode | TEXT | Indexed |
| carrier_vendor | TEXT | |
| total_weight_kg | FLOAT | |
| total_freight_cost_usd | FLOAT | |
| total_insurance_usd | FLOAT | |
| payment_terms | TEXT | |
| delivery_date | TEXT | |
| hs_code | TEXT | **Part 2** — Harmonized System code |
| port_of_loading | TEXT | **Part 2** — Origin port |
| port_of_discharge | TEXT | **Part 2** — Destination port |
| incoterms | TEXT | **Part 2** — e.g. CIF, FOB, EXW |
| description_of_goods | TEXT | **Part 2** — Primary goods description |
| extraction_confidence | FLOAT | 0.0–1.0 aggregate (fraction of fields present) |
| extracted_at | TEXT | datetime('now') default |
| confirmed_by_user | INTEGER | 0 = pending, 1 = confirmed |

**Relationships:** 1 → M with `extracted_line_items`

---

### `extracted_line_items`

Individual charge/goods lines within an extracted document.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| document_id | INTEGER FK | → extracted_documents.id (CASCADE DELETE) |
| description | TEXT | |
| quantity | INTEGER | |
| unit_price | FLOAT | |
| total_price | FLOAT | |
| confidence | FLOAT | 0.0–1.0 |

---

### `verification_results` *(Part 2)*

One row per SU → CG verification run. Stores the outcome of running the full pipeline against a trade document.

Minimum schema from assignment spec — extended with `customer_name` and `error_message`.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| shipment_id | TEXT | Generated UUID-based ID (e.g. SH-A1B2C3D4) |
| received_at | TEXT | ISO 8601 timestamp |
| customer_id | TEXT | Indexed — links to customer rules config |
| customer_name | TEXT | Display name from rules config |
| overall_status | TEXT | `approved` \| `amendment_required` \| `uncertain` \| `failed` |
| draft_reply | TEXT | LLM-generated email body (editable by CG) |
| error_message | TEXT | Populated only on `status = failed` |
| created_at | TEXT | datetime('now') default |

**Indexes:** `customer_id`, `overall_status`, `received_at`

**Relationships:** 1 → M with `verification_fields`

---

### `verification_fields` *(Part 2)*

One row per field checked in a verification run. This is the table the analytics agent queries for patterns like "which fields failed most often this week?".

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| verification_id | INTEGER FK | → verification_results.id (CASCADE DELETE) |
| name | TEXT | Field name (e.g. `hs_code`, `incoterms`) |
| extracted | TEXT | What the vision agent read from the document |
| expected | TEXT | What the customer rule requires |
| status | TEXT | `match` \| `mismatch` \| `uncertain` \| `no_rule` |
| confidence | FLOAT | 0.0–1.0 (converted from HIGH/MEDIUM/LOW/NOT_FOUND) |
| rule_description | TEXT | Human-readable rule that was applied |

**Indexes:** `verification_id`, `status`, `name`

---

### `_stats_cache`

Internal statistical baseline for anomaly detection. Computed at startup and refreshed after each seed operation.

| Column | Type | Notes |
|---|---|---|
| dimension | TEXT PK | e.g. `shipments_all`, `freight_air` |
| mean | FLOAT | |
| stddev | FLOAT | |
| p25 | FLOAT | |
| p75 | FLOAT | |
| iqr_fence_low | FLOAT | p25 - 1.5×IQR |
| iqr_fence_high | FLOAT | p75 + 1.5×IQR |

11 dimensions pre-computed across shipment counts, freight costs, and weights.

---

## Confidence Score Mapping

The extraction agent uses string confidence levels internally. The verification pipeline converts these to floats for storage and threshold comparison:

| String | Float | Meaning |
|---|---|---|
| HIGH | 0.9 | Clearly visible, unambiguous |
| MEDIUM | 0.6 | Present but partially obscured or inferred |
| LOW | 0.3 | Very hard to read, guessed, or uncertain |
| NOT_FOUND | 0.0 | Field absent from document |

**Uncertainty threshold** (configurable per customer in rules config): default `0.6`. Any field with confidence below this threshold is marked `uncertain` regardless of whether the extracted value appears to match the expected value.
