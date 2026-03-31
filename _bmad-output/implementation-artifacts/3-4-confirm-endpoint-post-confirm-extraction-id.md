# Story 3.4: Confirm Endpoint — POST /api/documents/confirm

Status: done

## Story

As a logistics operations analyst,
I want to confirm a reviewed extraction so it is persisted as a verified record in the data store,
So that the data becomes available for analytics queries.

## Acceptance Criteria

1. **Given** a valid `extraction_id` exists in `extracted_documents` with `confirmed_by_user=0`
   **When** `POST /api/documents/confirm` is called with any edited field values in `corrections`
   **Then** the `extracted_documents` row is updated: edited fields are applied and `confirmed_by_user` is set to `1` (FR21)
   **And** the response returns HTTP 200 with `{ "stored": true, "document_id": <id> }`

2. **Given** `POST /api/documents/confirm` is called
   **When** the code is inspected
   **Then** `ExtractionVerifier.validate_corrections()` runs before any SQLite write — no route commits without a Verifier pass

3. **Given** the confirmed record is stored
   **When** a subsequent `GET /api/schema` is called
   **Then** the `extracted_documents` row count reflects the record (it already existed; confirm does not add a row, but the row is now `confirmed_by_user=1` and fully queryable by analytics)

## Tasks / Subtasks

- [x] Task 1: Create `backend/app/schemas/documents.py` (AC: 1)
  - [x] Define `ConfirmRequest(BaseModel)` with `extraction_id: int` and `corrections: dict[str, str] | None = None`
  - [x] Define `ConfirmResponse(BaseModel)` with `stored: bool` and `document_id: int`

- [x] Task 2: Create `backend/app/agents/extraction/verifier.py` (AC: 2)
  - [x] Define `ExtractionVerifier` class with `validate_corrections(corrections, document) -> tuple[bool, str | None]`
  - [x] Validate: correction keys must be subset of allowed editable fields (see Dev Notes)
  - [x] Validate: `shipment_mode` value if present must be one of: `Air`, `Ocean`, `Truck`, `Air Charter`
  - [x] Return `(True, None)` on success; `(False, "<reason>")` on failure
  - [x] Log validation failures at WARNING level

- [x] Task 3: Create `backend/app/api/routes/documents.py` (AC: 1, 2)
  - [x] Define `router = APIRouter()`
  - [x] Implement `POST /confirm` route: `async def post_confirm(body: ConfirmRequest, db: Session = Depends(get_db)) -> ConfirmResponse`
  - [x] Look up document by `body.extraction_id`; return HTTP 404 if not found
  - [x] If `confirmed_by_user=1` already, return HTTP 409 with error `already_confirmed`
  - [x] Run `ExtractionVerifier().validate_corrections(body.corrections or {}, doc)` — if invalid, return HTTP 422 with error `invalid_corrections`
  - [x] Apply corrections: for each key/value pair, `setattr(doc, key, value)`
  - [x] Set `doc.confirmed_by_user = 1` and call `db.commit(); db.refresh(doc)`
  - [x] Return `ConfirmResponse(stored=True, document_id=doc.id)`
  - [x] Wrap in `try/except Exception` → return HTTP 500 with `ErrorResponse`

- [x] Task 4: Register documents router in `backend/app/main.py` (AC: 1)
  - [x] Add `from app.api.routes import documents` import
  - [x] Add `app.include_router(documents.router, prefix="/api/documents")` after existing routers

- [x] Task 5: Write tests in `backend/tests/test_story_3_4.py` (AC: 1, 2, 3)
  - [x] Test: `POST /api/documents/confirm` with valid `extraction_id` returns HTTP 200 `{ stored: true, document_id }`
  - [x] Test: After confirm, `db.query(ExtractedDocument).get(id).confirmed_by_user == 1`
  - [x] Test: Corrections are applied to the document row after confirm
  - [x] Test: Unknown `extraction_id` returns HTTP 404
  - [x] Test: Already-confirmed document returns HTTP 409
  - [x] Test: Invalid correction key (non-existent field) returns HTTP 422
  - [x] Test: Invalid `shipment_mode` vocabulary returns HTTP 422
  - [x] Test: `ExtractionVerifier.validate_corrections` with valid data returns `(True, None)` directly (unit test)
  - [x] Test: Endpoint appears in OpenAPI spec (`/api/documents/confirm`)

### Review Findings

- [x] [Review][Patch] `test_confirm_applies_corrections` missing response status assertion [backend/tests/test_story_3_4.py:~88] — added `assert resp.status_code == 200` before the DB state check
- [x] [Review][Patch] `validate_corrections` does not strip whitespace from `shipment_mode` value before vocabulary check [backend/app/agents/extraction/verifier.py:~114] — added `.strip()` to `mode` before the set membership test

- [x] [Review][Defer] `post_extract` returns HTTP 200 on unsupported file type [backend/app/api/routes/documents.py:~24] — deferred, Story 3.1 scope
- [x] [Review][Defer] `post_extract` returns HTTP 200 on extraction failure [backend/app/api/routes/documents.py:~57] — deferred, Story 3.1 scope
- [x] [Review][Defer] No `db.rollback()` on extraction failure in `post_extract` [backend/app/api/routes/documents.py:~52] — deferred, Story 3.1 scope
- [x] [Review][Defer] `post_extract` leaks raw exception message to client via `message=str(e)` [backend/app/api/routes/documents.py:~57] — deferred, Story 3.1 scope
- [x] [Review][Defer] No file-size limit before `await file.read()` — deferred, Story 3.1 scope
- [x] [Review][Defer] `_parse_line_items` `int()` cast raises `ValueError` on float strings like `"2.5"` [backend/app/agents/extraction/verifier.py:~95] — deferred, Story 3.1 scope
- [x] [Review][Defer] No tests for `post_extract` endpoint — deferred, Story 3.1 scope
- [x] [Review][Defer] `confirmed_by_user` uses magic integers 0/1 with no type safety [backend/app/models/extracted_document.py] — deferred, pre-existing model from Story 1.2
- [x] [Review][Defer] `ExtractionResponse.extraction_id=0` invalid sentinel on failure [backend/app/api/routes/documents.py:~30] — deferred, Story 3.1 scope
- [x] [Review][Defer] Numeric correction values not type-coerced before `setattr` (e.g. string `"not_a_number"` for Float column) — deferred, POC-acceptable per spec dev notes
- [x] [Review][Defer] `_HEADER_FIELDS` and `_ALLOWED_CORRECTION_FIELDS` are separately maintained duplicates — deferred, they serve distinct purposes that will diverge in Story 3.2
- [x] [Review][Defer] Frontend `ConfirmRequest.extraction_id: string` vs backend `int` type mismatch — deferred, pre-existing in `frontend/src/types/api.ts`
- [x] [Review][Defer] `engine` return value unused and unclosed in test methods — deferred, cosmetic, no functional impact

## Dev Notes

### File locations — critical, do not deviate

| Action | File |
|--------|------|
| **CREATE** schemas | `backend/app/schemas/documents.py` |
| **CREATE** verifier | `backend/app/agents/extraction/verifier.py` |
| **CREATE** route | `backend/app/api/routes/documents.py` |
| **MODIFY** main | `backend/app/main.py` — add import + include_router only |
| **CREATE** tests | `backend/tests/test_story_3_4.py` |
| **NO CHANGES** | `analytics.py`, `system.py`, `database.py`, any model file, any existing test |

### URL decision — architecture vs. epics discrepancy

Epics AC says `POST /confirm/{extraction_id}` (path param). Architecture and frontend types specify `POST /api/documents/confirm` with `extraction_id` in the request body.

**Decision: follow architecture + frontend types.** The route handler is:
```python
@router.post("/confirm", response_model=ConfirmResponse)
async def post_confirm(body: ConfirmRequest, db: Session = Depends(get_db)):
    ...
```
Registered as `app.include_router(documents.router, prefix="/api/documents")` → live at `POST /api/documents/confirm`.

### Pydantic schemas — `app/schemas/documents.py`

```python
from pydantic import BaseModel
from typing import Optional


class ConfirmRequest(BaseModel):
    extraction_id: int
    corrections: Optional[dict[str, str]] = None


class ConfirmResponse(BaseModel):
    stored: bool
    document_id: int
```

`extraction_id` is typed as `int` (matches `ExtractedDocument.id` primary key). Frontend sends it as a string; Pydantic coerces `"123"` → `123` by default.

`corrections` maps field name → new string value. Numeric fields (`total_weight_kg`, `total_freight_cost_usd`, `total_insurance_usd`) are sent as string and the Verifier/route should accept them as strings (SQLite will coerce; the column types are `Float` but `setattr` with a string representation is acceptable for this POC).

### ExtractionVerifier — `app/agents/extraction/verifier.py`

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ALLOWED_CORRECTION_FIELDS = {
    "invoice_number",
    "invoice_date",
    "shipper_name",
    "consignee_name",
    "origin_country",
    "destination_country",
    "shipment_mode",
    "carrier_vendor",
    "total_weight_kg",
    "total_freight_cost_usd",
    "total_insurance_usd",
    "payment_terms",
    "delivery_date",
}

_VALID_SHIPMENT_MODES = {"Air", "Ocean", "Truck", "Air Charter"}


class ExtractionVerifier:
    def validate_corrections(
        self,
        corrections: dict[str, str],
        document: object,
    ) -> tuple[bool, Optional[str]]:
        """Validate correction keys and vocabulary values. Returns (valid, error_message)."""
        invalid_keys = set(corrections.keys()) - _ALLOWED_CORRECTION_FIELDS
        if invalid_keys:
            msg = f"Invalid correction field(s): {', '.join(sorted(invalid_keys))}"
            logger.warning("ExtractionVerifier rejected corrections: %s", msg)
            return False, msg

        if "shipment_mode" in corrections:
            mode = corrections["shipment_mode"]
            if mode not in _VALID_SHIPMENT_MODES:
                msg = f"Invalid shipment_mode '{mode}'. Must be one of: {', '.join(sorted(_VALID_SHIPMENT_MODES))}"
                logger.warning("ExtractionVerifier rejected shipment_mode: %s", msg)
                return False, msg

        return True, None
```

**Design notes:**
- No LLM call — pure synchronous Python validation
- The `document` parameter is accepted but not currently used; it's in the signature to allow future field-level validation (e.g., checking date format) without changing the interface
- No import of `ExtractedDocument` model inside verifier — avoids circular imports; field set is a static constant

### Route implementation — `app/api/routes/documents.py`

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.extraction.verifier import ExtractionVerifier
from app.core.database import get_db
from app.models.extracted_document import ExtractedDocument
from app.schemas.documents import ConfirmRequest, ConfirmResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/confirm", response_model=ConfirmResponse)
async def post_confirm(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
) -> ConfirmResponse:
    doc = db.get(ExtractedDocument, body.extraction_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="extraction_id not found")

    if doc.confirmed_by_user == 1:
        raise HTTPException(status_code=409, detail="already_confirmed")

    verifier = ExtractionVerifier()
    corrections = body.corrections or {}
    valid, error_msg = verifier.validate_corrections(corrections, doc)
    if not valid:
        raise HTTPException(status_code=422, detail=error_msg)

    try:
        for key, value in corrections.items():
            setattr(doc, key, value)
        doc.confirmed_by_user = 1
        db.commit()
        db.refresh(doc)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to commit confirmation for extraction_id=%s: %s", body.extraction_id, exc)
        raise HTTPException(status_code=500, detail="internal_error")

    return ConfirmResponse(stored=True, document_id=doc.id)
```

**Key patterns used:**
- `db.get(ExtractedDocument, id)` — SQLAlchemy 2.x identity map lookup; preferred over `db.query(...).filter(...).first()`
- `db.rollback()` in except — clean up dirty session before re-raising
- `raise HTTPException` — triggers the global `http_exception_handler` in `main.py`, which wraps into `ErrorResponse` shape
- `Depends(get_db)` — standard DI, not inline `SessionLocal()`
- No `ModelClient`, no LLM calls

### main.py changes — minimal, surgical

Add exactly two lines to `backend/app/main.py`:

```python
# Add to the imports section (alongside existing: from app.api.routes import analytics, system)
from app.api.routes import analytics, system, documents  # add documents here

# Add after existing include_router calls
app.include_router(documents.router, prefix="/api/documents")
```

The combined import line is the safest approach — matches the existing `from app.api.routes import analytics, system` pattern.

### Testing pattern — `backend/tests/test_story_3_4.py`

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base
from app.models.extracted_document import ExtractedDocument
from app.agents.extraction.verifier import ExtractionVerifier


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, Factory


def _seed_doc(factory, confirmed=0):
    """Insert one ExtractedDocument row; return its id."""
    db = factory()
    try:
        doc = ExtractedDocument(
            source_filename="invoice.pdf",
            confirmed_by_user=confirmed,
            shipment_mode="Air",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


class TestConfirmEndpoint:
    def _get_client(self, factory):
        def override_get_db():
            db = factory()
            try:
                yield db
            finally:
                db.close()
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)

    def setup_method(self):
        app.dependency_overrides.clear()

    def test_confirm_valid_returns_200(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        resp = client.post("/api/documents/confirm", json={"extraction_id": doc_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["stored"] is True
        assert body["document_id"] == doc_id

    def test_confirm_sets_confirmed_by_user_1(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        client.post("/api/documents/confirm", json={"extraction_id": doc_id})
        db = factory()
        try:
            doc = db.get(ExtractedDocument, doc_id)
            assert doc.confirmed_by_user == 1
        finally:
            db.close()

    def test_confirm_applies_corrections(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        client.post(
            "/api/documents/confirm",
            json={"extraction_id": doc_id, "corrections": {"invoice_number": "INV-999"}},
        )
        db = factory()
        try:
            doc = db.get(ExtractedDocument, doc_id)
            assert doc.invoice_number == "INV-999"
        finally:
            db.close()

    def test_unknown_extraction_id_returns_404(self):
        engine, factory = _make_db()
        client = self._get_client(factory)
        resp = client.post("/api/documents/confirm", json={"extraction_id": 9999})
        assert resp.status_code == 404

    def test_already_confirmed_returns_409(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory, confirmed=1)
        client = self._get_client(factory)
        resp = client.post("/api/documents/confirm", json={"extraction_id": doc_id})
        assert resp.status_code == 409

    def test_invalid_correction_key_returns_422(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        resp = client.post(
            "/api/documents/confirm",
            json={"extraction_id": doc_id, "corrections": {"nonexistent_field": "value"}},
        )
        assert resp.status_code == 422

    def test_invalid_shipment_mode_returns_422(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        resp = client.post(
            "/api/documents/confirm",
            json={"extraction_id": doc_id, "corrections": {"shipment_mode": "InvalidMode"}},
        )
        assert resp.status_code == 422

    def test_endpoint_in_openapi_spec(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        assert "/api/documents/confirm" in spec["paths"]
        assert "post" in spec["paths"]["/api/documents/confirm"]


class TestExtractionVerifier:
    def test_valid_corrections_returns_true(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({"invoice_number": "INV-1"}, object())
        assert valid is True
        assert msg is None

    def test_empty_corrections_returns_true(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({}, object())
        assert valid is True

    def test_invalid_key_returns_false(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({"bad_field": "x"}, object())
        assert valid is False
        assert msg is not None

    def test_valid_shipment_mode_accepted(self):
        verifier = ExtractionVerifier()
        for mode in ("Air", "Ocean", "Truck", "Air Charter"):
            valid, _ = verifier.validate_corrections({"shipment_mode": mode}, object())
            assert valid is True

    def test_invalid_shipment_mode_rejected(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({"shipment_mode": "Rail"}, object())
        assert valid is False
        assert "Rail" in msg
```

### ExtractedDocument model — reference only, DO NOT MODIFY

```python
class ExtractedDocument(Base):
    __tablename__ = "extracted_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_filename = Column(Text, nullable=False)
    invoice_number = Column(Text)
    invoice_date = Column(Text)
    shipper_name = Column(Text)
    consignee_name = Column(Text)
    origin_country = Column(Text)
    destination_country = Column(Text)
    shipment_mode = Column(Text)
    carrier_vendor = Column(Text)
    total_weight_kg = Column(Float)
    total_freight_cost_usd = Column(Float)
    total_insurance_usd = Column(Float)
    payment_terms = Column(Text)
    delivery_date = Column(Text)
    extraction_confidence = Column(Float)
    extracted_at = Column(Text, server_default=text("(datetime('now'))"))
    confirmed_by_user = Column(Integer, default=0, server_default="0")
```

Seeding a test row requires only `source_filename` (the only `nullable=False` column besides `id`).

### Allowed editable correction fields

These 13 fields may appear as correction keys. Any other key → `ExtractionVerifier` rejects:

```
invoice_number, invoice_date, shipper_name, consignee_name, origin_country,
destination_country, shipment_mode, carrier_vendor, total_weight_kg,
total_freight_cost_usd, total_insurance_usd, payment_terms, delivery_date
```

Excluded (non-editable): `id`, `source_filename`, `extraction_confidence`, `extracted_at`, `confirmed_by_user`.

### Vocabulary constraint — shipment_mode

Valid values: `Air`, `Ocean`, `Truck`, `Air Charter`

This matches the normalisation vocabulary in Story 3.2 and the `shipments.shipment_mode` column vocabulary in the SCMS dataset. The Verifier enforces this to prevent linkage query breakage (FR25–FR28).

### What NOT to change

- `backend/app/models/extracted_document.py` — no changes; model is complete
- `backend/app/models/extracted_line_item.py` — no changes
- `backend/app/api/routes/analytics.py` — no changes
- `backend/app/api/routes/system.py` — no changes
- `backend/app/core/database.py` — no changes
- Any existing test file — no changes

### Previous story learnings (from Story 2.5)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must be the first import line in every test file — before any `from app.*` imports
- `TestClient(app)` triggers lifespan startup; if `backend/data/scms_shipments.csv` is missing this raises. Use `StaticPool` in-memory DB and override `get_db` dependency to skip file load concern — lifespan still runs, but the CSV load path reads the real CSV from `backend/data/`. Tests work because `app.dependency_overrides[get_db]` intercepts all route DB calls; the lifespan uses `SessionLocal()` directly (not `get_db`), so CSV loads to the real DB, not the in-memory one. This is acceptable for these tests.
- `app.dependency_overrides.clear()` in `setup_method` ensures no cross-test contamination
- `StaticPool` ensures all connections share one in-memory engine — rows seeded in `_seed_doc` are visible to the test client session
- `db.get(Model, pk)` is the SQLAlchemy 2.x identity-map lookup (replaces `db.query(Model).get(pk)` which is deprecated)

### AC3 clarification

AC3 says "`GET /api/schema` row count increases by 1 after confirm". This is only testable end-to-end when Story 3.1 (`POST /extract`) is implemented — that story creates the `extracted_documents` row before confirm is called. For this story's tests, we seed rows directly; the confirm endpoint updates `confirmed_by_user=1` on an existing row. The row was always counted in `GET /api/schema` (schema counts all rows regardless of confirmation status). AC3 is satisfied architecturally — no extra work needed here.

### References

- [Source: epics.md — Story 3.4, FR21]: "System persists confirmed extracted data with user edits applied"
- [Source: architecture.md — API naming patterns]: `/api/documents/confirm` is the canonical URL; `extraction_id` in body per `ConfirmRequest` Pydantic model
- [Source: frontend/src/types/api.ts]: `ConfirmRequest { extraction_id: string; corrections?: Record<string, string> }` and `ConfirmResponse { stored: boolean; document_id: number }`
- [Source: architecture.md — Verifier layer]: "gates all side effects"; "Verifier validates fields, normalises vocabulary, scores confidence"
- [Source: architecture.md — Error handling pattern]: all routes try/except, `HTTPException` triggers global handler → `ErrorResponse` shape
- [Source: architecture.md — agents/extraction/verifier.py]: separate file from executor, mandatory

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Routing prefix issue: linter kept toggling `router = APIRouter(prefix="/documents")` ↔ `router = APIRouter()`. Resolved by confirming with `python3 -c "from app.api.routes import documents; print(documents.router.prefix)"` that the actual prefix was empty, then using `prefix="/api/documents"` in `include_router`. Tests confirmed URL at `/api/documents/confirm`.

### Completion Notes List

- Added `ConfirmRequest(BaseModel)` and `ConfirmResponse(BaseModel)` to `backend/app/schemas/documents.py` (file pre-existed with stub schemas from a prior linter pass; appended the two new classes).
- Created `backend/app/agents/extraction/verifier.py` with `ExtractionVerifier.validate_corrections()` — pure synchronous validation, no LLM calls. Validates 13 allowed editable field names and `shipment_mode` vocabulary (`Air`, `Ocean`, `Truck`, `Air Charter`).
- Created `backend/app/api/routes/documents.py` with `POST /confirm` route. Uses `db.get(ExtractedDocument, id)` (SQLAlchemy 2.x identity-map). Returns 404/409/422/500 via `HTTPException` (triggers global `http_exception_handler` → `ErrorResponse` shape). `db.rollback()` on commit failure before re-raising.
- Modified `backend/app/main.py`: added `documents` to the import, added `app.include_router(documents.router, prefix="/api/documents")`.
- Created `backend/tests/test_story_3_4.py` with 13 tests (8 endpoint + 5 verifier unit). All 13 pass. Full regression: 265 tests, 0 failures.

### File List

- `backend/app/schemas/documents.py` (modified — added `ConfirmRequest`, `ConfirmResponse`)
- `backend/app/agents/extraction/verifier.py` (created)
- `backend/app/api/routes/documents.py` (created)
- `backend/app/main.py` (modified — added documents router import + include)
- `backend/tests/test_story_3_4.py` (created)

## Change Log

- 2026-03-30: Story 3.4 created — ready-for-dev
- 2026-03-30: Implemented Story 3.4 — POST /api/documents/confirm with ExtractionVerifier, 13 tests passing, 265 total passing
- 2026-03-30: Code review patches applied — 2 items fixed (test status assertion, shipment_mode whitespace strip), 291 total passing
