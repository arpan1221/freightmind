# Story 3.3: Confidence Scoring Per Field

Status: done

## Story

As a logistics operations analyst,
I want each extracted field to carry a confidence level of HIGH, MEDIUM, LOW, or NOT_FOUND,
So that I can immediately see which fields need my attention before confirming.

## Acceptance Criteria

1. **Given** the vision model returns extracted fields with confidence scores
   **When** the response is assembled
   **Then** each of the 14 fields and each line item field has a `confidence` value of `HIGH`, `MEDIUM`, `LOW`, or `NOT_FOUND` (FR13)

2. **Given** a field could not be found in the document
   **When** the response is assembled
   **Then** the field value is `null` and confidence is `NOT_FOUND`

3. **Given** a field has `LOW` or `NOT_FOUND` confidence
   **When** the extraction response is inspected
   **Then** a `low_confidence_fields` list in the response enumerates those field names for the frontend to flag (FR14)

## Tasks / Subtasks

- [x] Task 1: Add `ConfidenceLevel` enum to `app/schemas/common.py` (AC: 1, 2)
  - [x] Import `Enum` from Python `enum` stdlib
  - [x] Define `class ConfidenceLevel(str, Enum)` with values `HIGH`, `MEDIUM`, `LOW`, `NOT_FOUND` — always uppercase string literals
  - [x] Place BEFORE `ErrorResponse` class (shared foundation, depended on by documents.py)

- [x] Task 2: Create `app/schemas/documents.py` (AC: 1, 2, 3)
  - [x] Pre-existing from Story 3.1: `ExtractedField` (analogous to `FieldValue`), `ExtractedLineItemOut` (analogous to `LineItemResult`), `ExtractionResponse` — no changes needed

- [x] Task 3: Create `app/agents/extraction/verifier.py` with `ExtractionVerifier` class (AC: 1, 2, 3)
  - [x] Pre-existing from Story 3.1: `ExtractionVerifier` class with `verify()` and `validate_corrections()`
  - [x] Added `score_confidence(raw_fields, raw_line_items)` method returning `(dict[str, ExtractedField], list[ExtractedLineItemOut], list[str])`
  - [x] For each field: parse `confidence` string key → `ConfidenceLevel`; if value is `None` → force `NOT_FOUND`
  - [x] Coerce unknown/invalid confidence string to `LOW` (never raise — logger.debug)
  - [x] Line items: `NOT_FOUND` coerced to `LOW`; build `low_confidence_fields` for LOW/NOT_FOUND fields

- [x] Task 4: Write tests in `backend/tests/test_story_3_3.py` (AC: 1, 2, 3)
  - [x] Test: `ConfidenceLevel` has all four string values and is a str subclass
  - [x] Test: `ExtractedField` accepts valid confidence enum values and serialises as plain string
  - [x] Test: `ExtractionResponse.low_confidence_fields` defaults to empty list
  - [x] Test: `score_confidence` maps `"HIGH"` → `ConfidenceLevel.HIGH`, etc.
  - [x] Test: `score_confidence` — field with `value=None` gets confidence `NOT_FOUND` regardless of input
  - [x] Test: `score_confidence` — invalid/unknown confidence string coerced to `LOW`
  - [x] Test: `score_confidence` — LOW and NOT_FOUND fields appear in `low_confidence_fields`
  - [x] Test: `score_confidence` — HIGH and MEDIUM fields do NOT appear in `low_confidence_fields`
  - [x] Test: `score_confidence` — empty input → empty outputs (no crash)
  - [x] Test: `score_confidence` — line items with NOT_FOUND coerce to `LOW`

### Review Findings (AI)

#### Decision Needed

- [x] [Review][Decision] `score_confidence()` never called by the extraction route — resolved: Option A applied. Updated `extraction_fields.txt` to return per-field `{"value", "confidence"}` format; route now calls `score_confidence()` instead of `verify()`; `test_story_3_1.py` and `test_story_3_8.py` mocks updated. 309/309 tests pass.

#### Patches

- [x] [Review][Patch] Unguarded `int(qty)` / `float(up)` / `float(tp)` in `score_confidence()` can raise `ValueError`/`TypeError` on non-numeric LLM output [verifier.py] — wrapped in try/except, returning `None` on failure
- [x] [Review][Patch] `score_confidence()` stores numeric field values verbatim without calling `_coerce()` [verifier.py] — now calls `self._coerce(field_name, raw_value)` before confidence evaluation; also added `isinstance(raw, dict)` guard per field and per line item

#### Deferred

- [x] [Review][Defer] `validate_corrections()` does not validate numeric field types — string values written to Float DB columns [verifier.py] — deferred, pre-existing (Story 3.4 scope)
- [x] [Review][Defer] `low_confidence_fields` covers header fields only, not line items — deferred, pre-existing design choice, consistent with tests and ExtractionResponse schema
- [x] [Review][Defer] `_HEADER_FIELDS` and `_ALLOWED_CORRECTION_FIELDS` are fully duplicated — deferred, pre-existing drift risk
- [x] [Review][Defer] `_VALID_SHIPMENT_MODES` case-sensitive with no normalisation in `validate_corrections()` — deferred, pre-existing (Story 3.4 scope)
- [x] [Review][Defer] `_parse_line_items()` silently drops non-dict items with no log — deferred, pre-existing
- [x] [Review][Defer] `validate_corrections()` `document` parameter accepted but unused — deferred, pre-existing (Story 3.4 scope)
- [x] [Review][Defer] `int(qty)` silently truncates float quantities (`1.9 → 1`) — deferred, consistent with existing `_parse_line_items()` behavior
- [x] [Review][Defer] `validate_corrections()` accepts empty string corrections — deferred, pre-existing (Story 3.4 scope)
- [x] [Review][Defer] `score_confidence()` processes open field set (accepts any LLM-returned key) — deferred, intentional per spec Dev Notes

### Senior Developer Review (AI)

**Outcome:** Changes Requested
**Date:** 2026-03-30
**Layers run:** Blind Hunter, Edge Case Hunter, Acceptance Auditor

**Action Items:**
- [ ] [High] Resolve pipeline wiring decision: `score_confidence()` never reached in production
- [ ] [Med] Fix unguarded `int`/`float` conversion in `score_confidence()` (can raise on bad LLM output)
- [ ] [Med] Call `_coerce()` from `score_confidence()` for numeric fields

### Review Follow-ups (AI)

- [x] [AI-Review][Decision] Decide how `score_confidence()` is wired into the extraction pipeline (prompt format + route wiring) — resolved Option A
- [x] [AI-Review][Patch] Guard `int(qty)` / `float(up)` / `float(tp)` in `score_confidence()` with try/except
- [x] [AI-Review][Patch] Call `_coerce()` for numeric field values in `score_confidence()`

## Dev Notes

### File locations — critical, do not deviate

| Action | File |
|--------|------|
| **MODIFY** | `backend/app/schemas/common.py` — add `ConfidenceLevel` enum |
| **CREATE** | `backend/app/schemas/documents.py` — extraction Pydantic schemas |
| **CREATE** | `backend/app/agents/extraction/verifier.py` — confidence scoring |
| **CREATE** | `backend/tests/test_story_3_3.py` |
| **NO CHANGES** | `main.py`, `analytics.py`, `system.py`, `database.py`, any other file |

`app/agents/extraction/__init__.py` already exists — do NOT recreate it. The extraction route (`documents.py`) is Story 3.1's responsibility; Story 3.3 builds the scoring layer only.

### `ConfidenceLevel` enum — `app/schemas/common.py`

Add AFTER the imports, BEFORE `ErrorResponse`:

```python
from enum import Enum

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_FOUND = "NOT_FOUND"
```

`str` subclass is mandatory — Pydantic serialises it as a plain JSON string (`"HIGH"` not `{"value": "HIGH"}`), and it works as a dict key. The architecture spec (architecture.md line 447) requires exactly this pattern.

### Pydantic schemas — `app/schemas/documents.py`

```python
from typing import Any
from pydantic import BaseModel
from app.schemas.common import ConfidenceLevel


class FieldValue(BaseModel):
    value: Any | None = None
    confidence: ConfidenceLevel


class LineItemResult(BaseModel):
    description: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    total_price: float | None = None
    confidence: ConfidenceLevel


class ExtractionResponse(BaseModel):
    extraction_id: str
    fields: dict[str, FieldValue]
    line_items: list[LineItemResult] = []
    low_confidence_fields: list[str] = []
    error: str | None = None
```

**Why `value: Any | None`:** Column types are mixed — strings, floats, ints, dates as strings. Bare `Any` is correct here (same rationale as `sample_values: list` in `schema_info.py`). Pydantic serialises Python primitives to JSON without coercion.

**`error: str | None = None`:** Consistent with `AnalyticsQueryResponse` pattern. `None` on success.

### `ExtractionVerifier` — `app/agents/extraction/verifier.py`

```python
import logging
from app.schemas.common import ConfidenceLevel
from app.schemas.documents import FieldValue, LineItemResult

logger = logging.getLogger(__name__)

_VALID_CONFIDENCE = {c.value for c in ConfidenceLevel}


class ExtractionVerifier:
    def score_confidence(
        self,
        raw_fields: dict[str, dict],
        raw_line_items: list[dict],
    ) -> tuple[dict[str, FieldValue], list[LineItemResult], list[str]]:
        """
        Parse and validate confidence values from raw LLM extraction output.

        Args:
            raw_fields: {field_name: {"value": <any>, "confidence": <str>}}
            raw_line_items: [{"description": ..., "quantity": ..., "unit_price": ...,
                               "total_price": ..., "confidence": <str>}]

        Returns:
            (fields, line_items, low_confidence_fields)
        """
        fields: dict[str, FieldValue] = {}
        low_confidence_fields: list[str] = []

        for field_name, raw in raw_fields.items():
            value = raw.get("value")
            raw_conf = raw.get("confidence", "")

            if value is None:
                confidence = ConfidenceLevel.NOT_FOUND
            elif isinstance(raw_conf, str) and raw_conf.upper() in _VALID_CONFIDENCE:
                confidence = ConfidenceLevel(raw_conf.upper())
            else:
                logger.debug(
                    "score_confidence: unknown confidence %r for field %r — coercing to LOW",
                    raw_conf, field_name,
                )
                confidence = ConfidenceLevel.LOW

            fields[field_name] = FieldValue(value=value, confidence=confidence)
            if confidence in (ConfidenceLevel.LOW, ConfidenceLevel.NOT_FOUND):
                low_confidence_fields.append(field_name)

        line_items: list[LineItemResult] = []
        for raw_item in raw_line_items:
            raw_conf = raw_item.get("confidence", "")
            if isinstance(raw_conf, str) and raw_conf.upper() in _VALID_CONFIDENCE:
                confidence = ConfidenceLevel(raw_conf.upper())
            else:
                confidence = ConfidenceLevel.LOW
            # Line items never use NOT_FOUND — coerce missing to LOW
            if confidence == ConfidenceLevel.NOT_FOUND:
                confidence = ConfidenceLevel.LOW
            line_items.append(LineItemResult(
                description=raw_item.get("description"),
                quantity=raw_item.get("quantity"),
                unit_price=raw_item.get("unit_price"),
                total_price=raw_item.get("total_price"),
                confidence=confidence,
            ))

        return fields, line_items, low_confidence_fields
```

**Key rules:**
- `value is None` → `NOT_FOUND`, regardless of the `confidence` key in the raw dict
- Unknown/invalid confidence string → `LOW`, with a `logger.debug` (never raise — LLM output is untrusted)
- Line items: `NOT_FOUND` coerced to `LOW` (a line item is either present or absent from the response — if it's in the list it was found)
- Confidence string comparison is case-insensitive (`.upper()`) — the LLM may return `"high"` or `"High"`

### The 14 extracted fields

The `extracted_documents` DB schema (from DATASET_SCHEMA.md) defines these 13 directly storable fields:

| Field name | Type | Nullable |
|-----------|------|----------|
| `invoice_number` | Text | yes |
| `invoice_date` | Text | yes |
| `shipper_name` | Text | yes |
| `consignee_name` | Text | yes |
| `origin_country` | Text | yes |
| `destination_country` | Text | yes |
| `shipment_mode` | Text | yes |
| `carrier_vendor` | Text | yes |
| `total_weight_kg` | Float | yes |
| `total_freight_cost_usd` | Float | yes |
| `total_insurance_usd` | Float | yes |
| `payment_terms` | Text | yes |
| `delivery_date` | Text | yes |

FR11 specifies "14 defined structured fields". The 14th field will be confirmed when Story 3.1 authors the extraction prompt. Story 3.3 must support any field name — the `fields: dict[str, FieldValue]` schema is intentionally open (not a fixed set of 14 keys). Do NOT hardcode field names in the verifier.

### Testing pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from app.schemas.common import ConfidenceLevel
from app.schemas.documents import ExtractionResponse, FieldValue, LineItemResult
from app.agents.extraction.verifier import ExtractionVerifier


class TestConfidenceLevel:
    def test_is_str_subclass(self):
        assert issubclass(ConfidenceLevel, str)

    def test_all_four_values_exist(self):
        assert ConfidenceLevel.HIGH == "HIGH"
        assert ConfidenceLevel.MEDIUM == "MEDIUM"
        assert ConfidenceLevel.LOW == "LOW"
        assert ConfidenceLevel.NOT_FOUND == "NOT_FOUND"

    def test_serialises_as_plain_string(self):
        fv = FieldValue(value="Air", confidence=ConfidenceLevel.HIGH)
        data = fv.model_dump()
        assert data["confidence"] == "HIGH"
        assert isinstance(data["confidence"], str)


class TestExtractionResponseDefaults:
    def test_low_confidence_fields_defaults_to_empty(self):
        resp = ExtractionResponse(
            extraction_id="abc123",
            fields={"invoice_number": FieldValue(value="INV-001", confidence=ConfidenceLevel.HIGH)},
        )
        assert resp.low_confidence_fields == []
        assert resp.line_items == []
        assert resp.error is None


class TestExtractionVerifierScoreConfidence:
    def setup_method(self):
        self.verifier = ExtractionVerifier()

    def test_high_confidence_mapped_correctly(self):
        raw = {"invoice_number": {"value": "INV-001", "confidence": "HIGH"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["invoice_number"].confidence == ConfidenceLevel.HIGH
        assert "invoice_number" not in low

    def test_medium_confidence_mapped_correctly(self):
        raw = {"payment_terms": {"value": "NET30", "confidence": "MEDIUM"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["payment_terms"].confidence == ConfidenceLevel.MEDIUM
        assert "payment_terms" not in low

    def test_low_confidence_appears_in_low_confidence_fields(self):
        raw = {"total_insurance_usd": {"value": 150.0, "confidence": "LOW"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["total_insurance_usd"].confidence == ConfidenceLevel.LOW
        assert "total_insurance_usd" in low

    def test_null_value_forces_not_found_regardless_of_confidence(self):
        raw = {"shipper_name": {"value": None, "confidence": "HIGH"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["shipper_name"].confidence == ConfidenceLevel.NOT_FOUND
        assert "shipper_name" in low

    def test_not_found_confidence_appears_in_low_confidence_fields(self):
        raw = {"carrier_vendor": {"value": None, "confidence": "NOT_FOUND"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["carrier_vendor"].confidence == ConfidenceLevel.NOT_FOUND
        assert "carrier_vendor" in low

    def test_invalid_confidence_string_coerced_to_low(self):
        raw = {"invoice_date": {"value": "2024-01-15", "confidence": "UNSURE"}}
        fields, _, low = self.verifier.score_confidence(raw, [])
        assert fields["invoice_date"].confidence == ConfidenceLevel.LOW
        assert "invoice_date" in low

    def test_confidence_comparison_case_insensitive(self):
        raw = {"destination_country": {"value": "Nigeria", "confidence": "high"}}
        fields, _, _ = self.verifier.score_confidence(raw, [])
        assert fields["destination_country"].confidence == ConfidenceLevel.HIGH

    def test_high_medium_not_in_low_confidence_fields(self):
        raw = {
            "invoice_number": {"value": "INV-001", "confidence": "HIGH"},
            "payment_terms": {"value": "NET30", "confidence": "MEDIUM"},
        }
        _, _, low = self.verifier.score_confidence(raw, [])
        assert low == []

    def test_empty_input_returns_empty_outputs(self):
        fields, line_items, low = self.verifier.score_confidence({}, [])
        assert fields == {}
        assert line_items == []
        assert low == []

    def test_line_item_null_value_coerced_to_low_not_not_found(self):
        raw_items = [{"description": None, "quantity": None, "unit_price": None, "total_price": None, "confidence": "LOW"}]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].confidence == ConfidenceLevel.LOW

    def test_line_item_not_found_coerced_to_low(self):
        raw_items = [{"description": "ARV tablets", "quantity": 100, "unit_price": 5.0, "total_price": 500.0, "confidence": "NOT_FOUND"}]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].confidence == ConfidenceLevel.LOW

    def test_line_item_fields_populated_correctly(self):
        raw_items = [{"description": "ARV tablets", "quantity": 50, "unit_price": 10.0, "total_price": 500.0, "confidence": "HIGH"}]
        _, line_items, _ = self.verifier.score_confidence({}, raw_items)
        assert line_items[0].description == "ARV tablets"
        assert line_items[0].quantity == 50
        assert line_items[0].confidence == ConfidenceLevel.HIGH
```

### What this story does NOT implement

- **No extraction route** (`POST /api/documents/extract`) — Story 3.1
- **No PDF/image upload handling** — Story 3.1
- **No vision LLM call** — Story 3.1
- **No normalisation logic** (mode/country/date/weight) — Story 3.2
- **No `main.py` changes** — Story 3.1 registers `documents.py` router
- **No DB writes** — Story 3.4 (confirm endpoint)

`ExtractionVerifier.score_confidence()` is a pure function — no DB access, no LLM calls, no I/O. Story 3.2 will add `ExtractionVerifier.normalise()` to the same class. Story 3.1 will call `verifier.normalise()` + `verifier.score_confidence()` in sequence.

### Dependency note

Stories 3.1 and 3.2 are NOT prerequisites for implementing Story 3.3. This story's scope (schemas + scoring function) is fully testable in isolation. However, Stories 3.1 and 3.2 must be complete before the full extraction pipeline runs end-to-end.

### `app/schemas/common.py` — current state

```python
# Current file — add ConfidenceLevel BEFORE ErrorResponse:
from pydantic import BaseModel
from typing import Optional
from enum import Enum  # ← ADD this import


class ConfidenceLevel(str, Enum):  # ← ADD this class
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_FOUND = "NOT_FOUND"


class ErrorResponse(BaseModel):
    error: Optional[str] = None
    message: Optional[str] = None
    retry_after: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    model: str
```

### Epic 3 context — what comes before and after

| Story | Scope | Requires 3.3? |
|-------|-------|---------------|
| 3.1 | File upload endpoint, vision LLM call, pipeline wiring | YES — uses `ExtractionVerifier` + `ExtractionResponse` |
| 3.2 | Normalisation (mode/country/date/weight) in verifier | NO — parallel to 3.3 |
| 3.3 | **This story** — confidence schemas + scoring | — |
| 3.4 | Confirm endpoint — writes confirmed extraction to DB | YES — needs `ExtractionResponse` |

Stories 3.1–3.3 can be implemented in any order. Story 3.1 requires both 3.2 and 3.3 to be complete before it can wire the full pipeline.

### Previous learnings from Epic 2 (applicable patterns)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` BEFORE any `app.*` import in every test file
- Test class pattern: `class Test<Feature>:` with `setup_method` for instance setup
- `ConfidenceLevel(str, Enum)` — str subclass is required, not optional — ensures JSON serialisation works without custom encoders
- All exception handling in agent classes uses `logger.debug(...)` not `logger.warning(...)` for graceful degradation on bad LLM output (see `_count_null_exclusions` in analytics.py)
- Never raise from agent methods on invalid LLM output — coerce to safe defaults

### References

- [Source: epics.md — Story 3.3, FR13]: "System assigns a confidence level (HIGH, MEDIUM, LOW, or NOT_FOUND) to each extracted field"
- [Source: epics.md — Story 3.3, FR14]: "System visually distinguishes LOW confidence and NOT_FOUND fields from HIGH/MEDIUM"
- [Source: architecture.md — line 447]: `ConfidenceLevel(str, Enum)` with exact uppercase string values
- [Source: architecture.md — agents/extraction/verifier.py]: "Mode/country normalisation, confidence scoring"
- [Source: architecture.md — schemas/common.py]: "`ConfidenceLevel` enum (shared)" — must live in common.py
- [Source: architecture.md — schemas/documents.py]: "`ExtractionResponse, ConfirmRequest/Response`"
- [Source: prd.md — Endpoint Spec]: `fields: {field_name: {value, confidence}}`, `line_items: [{..., confidence}]`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — 19/19 new tests passed on first run; 284/284 total (no regressions).

### Completion Notes List

- Story spec conflicted with Stories 3.1/3.2 pre-existing implementation. Adapted without breaking existing code.
- `ConfidenceLevel` changed from `Literal[...]` to `class ConfidenceLevel(str, Enum)` in `common.py`. Pydantic v2 coerces string literals automatically — all 265 prior tests still pass.
- `documents.py` and `verifier.py` already existed from Story 3.1. `ExtractedField`/`ExtractedLineItemOut` serve as `FieldValue`/`LineItemResult` equivalents.
- Added `score_confidence()` to `ExtractionVerifier` — the key new functionality: parses per-field LLM confidence values, coerces unknowns to LOW, forces null values to NOT_FOUND, keeps line items NOT_FOUND-free.
- 19 tests cover all AC scenarios including case-insensitive matching, coercion, empty input, and the NOT_FOUND → LOW line item rule.

### File List

- `backend/app/schemas/common.py` — `ConfidenceLevel` changed from Literal to `(str, Enum)`
- `backend/app/agents/extraction/verifier.py` — added `score_confidence()` method + `_VALID_CONFIDENCE` set + `ConfidenceLevel` import
- `backend/tests/test_story_3_3.py` — 19 new tests

## Change Log

- 2026-03-30: Story 3.3 implemented — ConfidenceLevel enum + score_confidence() added to ExtractionVerifier
