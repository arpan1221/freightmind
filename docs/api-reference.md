# FreightMind — API Reference

All endpoints are prefixed with `/api`. Base URL: `http://localhost:8000` (local) or the Render deployment URL.

---

## Analytics

### `POST /api/query`

Run a natural language question against the dataset.

**Request:**
```json
{
  "question": "Which country had the highest average freight cost last quarter?",
  "previous_sql": null
}
```

**Response:**
```json
{
  "answer": "Nigeria had the highest average freight cost at $4,821 per shipment.",
  "sql": "SELECT country, AVG(freight_cost_usd) as avg_cost FROM shipments GROUP BY country ORDER BY avg_cost DESC LIMIT 1",
  "results": [{"country": "Nigeria", "avg_cost": 4821.3}],
  "chart": {"type": "bar", "x": "country", "y": "avg_cost"},
  "anomaly_note": null
}
```

**Error types:** `unsafe_sql` (422), `sql_execution_error` (400), `rate_limit` (429), `model_unavailable` (503)

---

### `GET /api/schema`

Returns table metadata for all tables in the database.

**Response:**
```json
{
  "tables": [
    {
      "table_name": "shipments",
      "columns": [{"name": "country", "type": "TEXT"}, ...],
      "row_count": 10324,
      "indexes": ["idx_country", "idx_shipment_mode"]
    }
  ]
}
```

---

### `GET /api/stats/live`

Live row counts for dashboard polling (every 5s when live seeding is active).

**Response:**
```json
{
  "shipments": 10324,
  "extracted_documents": 12,
  "extracted_line_items": 87,
  "live_seeding_active": false,
  "live_seeding_interval_seconds": 0
}
```

---

## Documents (Part 1)

### `POST /api/documents/extract`

Upload a trade document for field extraction.

**Request:** `multipart/form-data`
- `file`: PDF, PNG, or JPEG (max 10 MB)

**Response:**
```json
{
  "extraction_id": 42,
  "filename": "invoice_march.pdf",
  "fields": {
    "invoice_number": {"value": "INV-2024-SH-7842", "confidence": "HIGH"},
    "hs_code":        {"value": "8471.30.00",        "confidence": "HIGH"},
    "incoterms":      {"value": "CIF",               "confidence": "MEDIUM"},
    "consignee_name": {"value": "GlobalTech Industries Ltd.", "confidence": "HIGH"}
  },
  "line_items": [{"description": "Laptop Computers", "quantity": 200, "unit_price": 850.0, "total_price": 170000.0, "confidence": "HIGH"}],
  "low_confidence_fields": ["incoterms"]
}
```

**Errors:** 415 (unsupported type), 413 (too large), 500 (extraction failed)

---

### `POST /api/documents/confirm`

Confirm an extracted document (with optional corrections).

**Request:**
```json
{
  "extraction_id": 42,
  "corrections": {"shipment_mode": "Ocean"}
}
```

**Response:**
```json
{"stored": true, "document_id": 42}
```

**Errors:** 404 (not found), 409 (already confirmed), 422 (invalid correction field/value)

---

### `GET /api/documents/pending`

List unconfirmed extractions, newest first.

**Response:** `{"extractions": [ExtractedDocumentSummary, ...]}`

---

### `GET /api/documents/extractions`

List confirmed extractions. Supports `?limit=100&offset=0` pagination.

---

### `DELETE /api/documents/extractions/{extraction_id}`

Discard an unconfirmed extraction. No-op if already confirmed or not found. Returns 204.

---

## Verification (Part 2)

### `POST /api/verify/submit`

**Trigger:** SU document arrives. Runs the full verification pipeline synchronously.

**Request:** `multipart/form-data`
- `file`: PDF, PNG, or JPEG
- `customer_id`: string (default: `DEMO_CUSTOMER_001`)

**Response:**
```json
{
  "verification_id": 1,
  "shipment_id": "SH-A1B2C3D4",
  "received_at": "2026-04-09T05:45:00Z",
  "customer_id": "DEMO_CUSTOMER_001",
  "customer_name": "GlobalTech Industries",
  "overall_status": "amendment_required",
  "fields": [
    {
      "name": "hs_code",
      "extracted": "8471.40.00",
      "expected": "8471.30.00",
      "status": "mismatch",
      "confidence": 0.9,
      "rule_description": "Laptop computers HS code per customs agreement CA-2024-GT"
    },
    {
      "name": "incoterms",
      "extracted": "FOB",
      "expected": "CIF",
      "status": "mismatch",
      "confidence": 0.9,
      "rule_description": "Cost, Insurance, Freight — required per contract clause 4.2"
    }
  ],
  "draft_reply": "Dear Shipping Unit,\n\nWe have reviewed...",
  "error": null
}
```

**On failure** (corrupted file, LLM down, missing config): returns same schema with `overall_status: "failed"` and `error` populated. Always persisted to DB. Never crashes.

---

### `GET /api/verify/result/{verification_id}`

Retrieve a stored verification result by ID.

---

### `GET /api/verify/queue`

List recent verification results, newest first. Supports `?limit=50&offset=0`.

**Response:**
```json
{
  "verifications": [
    {
      "verification_id": 1,
      "shipment_id": "SH-A1B2C3D4",
      "received_at": "2026-04-09T05:45:00Z",
      "customer_id": "DEMO_CUSTOMER_001",
      "customer_name": "GlobalTech Industries",
      "overall_status": "amendment_required",
      "field_count": 7,
      "mismatch_count": 2
    }
  ]
}
```

---

## System

### `GET /api/health`

```json
{"status": "ok", "database": "connected", "model": "available"}
```

---

## Error Envelope

All errors use a consistent envelope:

```json
{
  "error_type": "rate_limit",
  "message": "OpenRouter rate limit reached. Retry in 42 seconds.",
  "retry_after": 42,
  "detail": {}
}
```

`error_type` values: `http_error`, `validation_error`, `unsafe_sql`, `sql_execution_error`, `database_unavailable`, `rate_limit`, `model_unavailable`, `internal_error`
