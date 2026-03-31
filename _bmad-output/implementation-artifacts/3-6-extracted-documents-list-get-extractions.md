# Story 3.6: Extracted Documents List — GET /api/documents/extractions

Status: done

## Story

As a logistics operations analyst,
I want to view a list of all previously confirmed extracted documents,
So that I can see what invoice data has been added to the system.

## Acceptance Criteria

1. **Given** at least one confirmed extraction exists in the database
   **When** `GET /api/documents/extractions` is called
   **Then** the response returns a list of records with `confirmed_by_user=1`, including `extraction_id`, `filename`, `extracted_at`, and key field values (FR24)

2. **Given** no confirmed extractions exist in the database
   **When** `GET /api/documents/extractions` is called
   **Then** the response returns an empty `extractions` list — HTTP 200, not an error

3. **Given** both confirmed and unconfirmed extractions exist
   **When** `GET /api/documents/extractions` is called
   **Then** only `confirmed_by_user=1` records appear in the response — unconfirmed docs are excluded

## Tasks / Subtasks

- [x] Task 1: Add list schemas to `backend/app/schemas/documents.py` (AC: 1)
  - [x] Define `ExtractedDocumentSummary(BaseModel)` with fields: `extraction_id: int`, `filename: str`, `extracted_at: str | None`, `invoice_number: str | None`, `invoice_date: str | None`, `shipment_mode: str | None`, `destination_country: str | None`, `total_freight_cost_usd: float | None`
  - [x] Define `ExtractionListResponse(BaseModel)` with `extractions: list[ExtractedDocumentSummary]`

- [x] Task 2: Add `GET /extractions` route to `backend/app/api/routes/documents.py` (AC: 1, 2, 3)
  - [x] Add `GET /extractions` route: `async def get_extractions(db: Session = Depends(get_db)) -> ExtractionListResponse`
  - [x] Query `db.query(ExtractedDocument).filter(ExtractedDocument.confirmed_by_user == 1).order_by(ExtractedDocument.id.desc()).all()`
  - [x] Map each document to `ExtractedDocumentSummary` and return `ExtractionListResponse(extractions=[...])`
  - [x] Wrap in `try/except Exception` → return HTTP 500 via `raise HTTPException(status_code=500, detail="internal_error")`

- [x] Task 3: Write tests in `backend/tests/test_story_3_6.py` (AC: 1, 2, 3)
  - [x] Test: `GET /api/documents/extractions` returns HTTP 200 with `{ "extractions": [] }` when no confirmed docs
  - [x] Test: Confirmed document appears in list with correct `extraction_id`, `filename` values
  - [x] Test: Unconfirmed document (`confirmed_by_user=0`) is excluded from list
  - [x] Test: Multiple confirmed docs all appear; unconfirmed doc still excluded
  - [x] Test: Response includes `extracted_at`, `invoice_number`, `shipment_mode`, `destination_country`, `total_freight_cost_usd` fields
  - [x] Test: Endpoint appears in OpenAPI spec (`/api/documents/extractions`)

### Review Findings

- [x] [Review][Patch] Missing ordering test — no test seeds 2+ confirmed docs and asserts newest-first (`id.desc()`) ordering [backend/tests/test_story_3_6.py]
- [x] [Review][Defer] No pagination on unbounded `.all()` query [backend/app/api/routes/documents.py] — deferred, pre-existing; not in scope for this story, pagination is a future concern
- [x] [Review][Defer] `except Exception` breadth converts all failures to `500 internal_error` [backend/app/api/routes/documents.py] — deferred, spec-mandated behavior
- [x] [Review][Defer] `setup_method` clears overrides but `teardown_method` would be safer [backend/tests/test_story_3_6.py] — deferred, pre-existing test pattern consistent with codebase
- [x] [Review][Defer] `total_freight_cost_usd` NaN/Inf not guarded — IEEE 754 specials pass Pydantic but can break JSON serialization [backend/app/api/routes/documents.py] — deferred, pre-existing concern across all float fields
- [x] [Review][Defer] No auth/authentication on `GET /extractions` endpoint [backend/app/api/routes/documents.py] — deferred, pre-existing architectural decision; no auth on any route in this project
- [x] [Review][Defer] `confirmed_by_user IS NULL` rows silently excluded [backend/app/api/routes/documents.py] — deferred, pre-existing DB model concern; raw SQL inserts bypass ORM defaults
- [x] [Review][Defer] `invoice_date` no format validation — free-form string from LLM extraction [backend/app/schemas/documents.py] — deferred, pre-existing pattern across all string date fields
- [x] [Review][Defer] `source_filename` nullable=False but a NULL value from raw SQL would cause 500 in blanket except [backend/app/api/routes/documents.py] — deferred, pre-existing DB constraint concern

## Dev Notes

### File locations — critical, do not deviate

| Action | File |
|--------|------|
| **MODIFY** schemas | `backend/app/schemas/documents.py` — append two new classes |
| **MODIFY** route | `backend/app/api/routes/documents.py` — append `GET /extractions` route |
| **CREATE** tests | `backend/tests/test_story_3_6.py` |
| **NO CHANGES** | `main.py`, `system.py`, `analytics.py`, `database.py`, any model file, any existing test |

`main.py` already registers `documents.router` with `prefix="/api"`. The router's own `prefix="/documents"` makes routes live at `/api/documents/*`. Adding `/extractions` to `documents.py` automatically exposes `GET /api/documents/extractions` — no `main.py` changes needed.

### URL decision

Architecture says `GET /list` in the file comment, but epics say `GET /extractions`. Decision: follow the epics — `/extractions` is a proper resource noun (consistent with REST conventions) and matches FR24 wording. Full path: `GET /api/documents/extractions`.

### Pydantic schemas — append to `app/schemas/documents.py`

```python
class ExtractedDocumentSummary(BaseModel):
    extraction_id: int
    filename: str
    extracted_at: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    shipment_mode: str | None = None
    destination_country: str | None = None
    total_freight_cost_usd: float | None = None


class ExtractionListResponse(BaseModel):
    extractions: list[ExtractedDocumentSummary]
```

**"Key field values" (FR24):** The spec says "extraction_id, filename, extracted_at, and key field values." The five key fields selected are: `invoice_number`, `invoice_date`, `shipment_mode`, `destination_country`, `total_freight_cost_usd`. These cover document identity, timing, logistics routing, and cost — sufficient for a list view without returning all 14 fields.

`extracted_at` maps to `ExtractedDocument.extracted_at` (SQLite datetime string, e.g. `"2026-03-30 12:00:00"`). It may be `None` in test rows seeded without `extracted_at`.

### Route implementation — append to `app/api/routes/documents.py`

Add these imports if not already present (check file before adding):
```python
from app.schemas.documents import ..., ExtractionListResponse, ExtractedDocumentSummary
```

Add the route:
```python
@router.get("/extractions", response_model=ExtractionListResponse)
async def get_extractions(
    db: Session = Depends(get_db),
) -> ExtractionListResponse:
    """Return all confirmed extracted documents ordered newest first."""
    try:
        docs = (
            db.query(ExtractedDocument)
            .filter(ExtractedDocument.confirmed_by_user == 1)
            .order_by(ExtractedDocument.id.desc())
            .all()
        )
        return ExtractionListResponse(
            extractions=[
                ExtractedDocumentSummary(
                    extraction_id=doc.id,
                    filename=doc.source_filename,
                    extracted_at=doc.extracted_at,
                    invoice_number=doc.invoice_number,
                    invoice_date=doc.invoice_date,
                    shipment_mode=doc.shipment_mode,
                    destination_country=doc.destination_country,
                    total_freight_cost_usd=doc.total_freight_cost_usd,
                )
                for doc in docs
            ]
        )
    except Exception as exc:
        logger.error("Failed to list extractions: %s", exc)
        raise HTTPException(status_code=500, detail="internal_error")
```

**Key patterns:**
- `Depends(get_db)` — not inline `SessionLocal()`. Consistent with all other routes.
- `.filter(ExtractedDocument.confirmed_by_user == 1)` — integer comparison (model uses int, not bool).
- `.order_by(ExtractedDocument.id.desc())` — newest-first by primary key (monotonically increasing autoincrement).
- No LLM calls, no `ModelClient`. Pure DB read.
- `db.query(Model)` — SQLAlchemy 1.x style query API (consistent with the project; `db.get()` is used only for PK lookup in confirm route, not for filtered queries).

### Import update for `documents.py` route file

The route file already imports `ConfirmRequest, ConfirmResponse, ExtractionResponse`. Update the import line to include the new schemas:

```python
from app.schemas.documents import (
    ConfirmRequest,
    ConfirmResponse,
    ExtractionListResponse,
    ExtractionResponse,
    ExtractedDocumentSummary,
)
```

### Testing pattern — `backend/tests/test_story_3_6.py`

```python
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base
from app.models.extracted_document import ExtractedDocument


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, autocommit=False, autoflush=False)


def _seed_doc(factory, confirmed=1, **kwargs):
    """Insert one ExtractedDocument row and return its id."""
    db = factory()
    try:
        doc = ExtractedDocument(
            source_filename=kwargs.get("source_filename", "invoice.pdf"),
            confirmed_by_user=confirmed,
            shipment_mode=kwargs.get("shipment_mode", "Air"),
            destination_country=kwargs.get("destination_country", "Nigeria"),
            invoice_number=kwargs.get("invoice_number", "INV-001"),
            total_freight_cost_usd=kwargs.get("total_freight_cost_usd", 1500.0),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


class TestExtractionListEndpoint:
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

    def test_empty_list_when_no_confirmed_docs(self):
        factory = _make_db()
        client = self._get_client(factory)
        resp = client.get("/api/documents/extractions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["extractions"] == []

    def test_confirmed_doc_appears_in_list(self):
        factory = _make_db()
        doc_id = _seed_doc(factory, confirmed=1, source_filename="bill.pdf")
        client = self._get_client(factory)
        resp = client.get("/api/documents/extractions")
        assert resp.status_code == 200
        items = resp.json()["extractions"]
        assert len(items) == 1
        assert items[0]["extraction_id"] == doc_id
        assert items[0]["filename"] == "bill.pdf"

    def test_unconfirmed_doc_excluded(self):
        factory = _make_db()
        _seed_doc(factory, confirmed=0)
        client = self._get_client(factory)
        resp = client.get("/api/documents/extractions")
        assert resp.status_code == 200
        assert resp.json()["extractions"] == []

    def test_only_confirmed_docs_returned_when_mixed(self):
        factory = _make_db()
        confirmed_id = _seed_doc(factory, confirmed=1, source_filename="confirmed.pdf")
        _seed_doc(factory, confirmed=0, source_filename="pending.pdf")
        client = self._get_client(factory)
        resp = client.get("/api/documents/extractions")
        assert resp.status_code == 200
        items = resp.json()["extractions"]
        assert len(items) == 1
        assert items[0]["extraction_id"] == confirmed_id

    def test_response_includes_key_fields(self):
        factory = _make_db()
        _seed_doc(
            factory,
            confirmed=1,
            source_filename="inv.pdf",
            invoice_number="INV-999",
            shipment_mode="Ocean",
            destination_country="Kenya",
            total_freight_cost_usd=2500.0,
        )
        client = self._get_client(factory)
        items = client.get("/api/documents/extractions").json()["extractions"]
        assert len(items) == 1
        item = items[0]
        assert item["invoice_number"] == "INV-999"
        assert item["shipment_mode"] == "Ocean"
        assert item["destination_country"] == "Kenya"
        assert item["total_freight_cost_usd"] == 2500.0
        assert "extracted_at" in item  # present (may be None in test DB)

    def test_endpoint_in_openapi_spec(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        assert "/api/documents/extractions" in spec["paths"]
        assert "get" in spec["paths"]["/api/documents/extractions"]
```

### ExtractedDocument model — reference only, DO NOT MODIFY

Only `source_filename` is `nullable=False`. All other columns default to `None`. The `extracted_at` column has a SQLite `server_default` of `(datetime('now'))` — in tests seeded via ORM (not raw SQL), it may be `None` unless the test explicitly sets it or inserts via raw SQL. Tests should use `"extracted_at" in item` rather than asserting a specific value.

### What NOT to change

- `backend/app/main.py` — no changes needed; documents router already registered
- `backend/app/models/extracted_document.py` — no changes
- `backend/app/api/routes/analytics.py` — no changes
- `backend/app/api/routes/system.py` — no changes
- Any existing test file — no changes

### Previous story learnings (from Stories 3.4, 2.5)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must be the first two lines in every test file — before any `from app.*` imports.
- `app.dependency_overrides.clear()` in `setup_method` prevents cross-test contamination.
- `StaticPool` ensures all in-process connections share one in-memory engine — rows seeded in `_seed_doc` are visible to the TestClient's DB session.
- `db.query(Model)` style (not `db.execute(select(Model))`) — consistent with how `get_schema` accesses data in this project; SQLAlchemy 1.x query API in use.
- The linter will likely add imports to `documents.py` — check the file state before and after writing.

### References

- [Source: epics.md — Story 3.6, FR24]: "User can view a list of all previously confirmed extracted documents"
- [Source: epics.md — Story 3.6 AC1]: Response includes `extraction_id`, `filename`, `extracted_at`, and key field values
- [Source: architecture.md — documents.py]: `GET /list` (using `/extractions` per epics)
- [Source: architecture.md — API naming patterns]: `GET /api/documents/extractions`
- [Source: frontend types]: No list type defined yet — Story 3.7 will add `ExtractionListItem` to `types/api.ts`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Import error in `verifier.py`: `_VALID_CONFIDENCE = {c.value for c in ConfidenceLevel}` failed because `ConfidenceLevel` is a `Literal`, not an Enum. Linter had already resolved this to `set(get_args(ConfidenceLevel))` before the fix was applied.

### Completion Notes List

- Appended `ExtractedDocumentSummary` and `ExtractionListResponse` to `backend/app/schemas/documents.py`
- Updated import in `documents.py` route file to include the two new schema classes
- Appended `GET /extractions` route to `backend/app/api/routes/documents.py` — pure DB read, no LLM calls, filters `confirmed_by_user == 1`, orders by `id.desc()`
- Created `backend/tests/test_story_3_6.py` with 6 tests covering all ACs; all 6 pass
- No `main.py` changes — documents router already registered with `prefix="/api"`

### File List

- backend/app/schemas/documents.py
- backend/app/api/routes/documents.py
- backend/tests/test_story_3_6.py

## Change Log

- 2026-03-30: Story 3.6 created — ready-for-dev
- 2026-03-30: Story 3.6 implemented — status → review
