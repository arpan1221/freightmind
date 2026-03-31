# Story 3.5: Cancel endpoint — DELETE /extract/{extraction_id}

Status: done

## Story

As a logistics operations analyst,
I want to cancel an extraction review so no data is stored,
So that I can discard a bad upload without polluting the database.

## Acceptance Criteria

1. **Given** a valid `extraction_id` exists with `confirmed_by_user=0`
   **When** `DELETE /extract/{extraction_id}` is called
   **Then** the row is deleted from `extracted_documents` and associated `extracted_line_items` rows are also deleted (FR22)
   **And** the response returns HTTP 200 confirming deletion

2. **Given** an unknown `extraction_id` is provided
   **When** `DELETE /extract/{extraction_id}` is called
   **Then** the response returns a structured error with HTTP 404 — no crash

## Tasks / Subtasks

- [x] Task 1: Create response schema (AC: 1)
  - [x] Add `DeleteExtractionResponse` to `backend/app/schemas/extraction.py` (create file): `extraction_id: int`, `deleted: bool = True`, `message: str`

- [x] Task 2: Implement the DELETE route (AC: 1, 2)
  - [x] Created `backend/app/api/routes/extraction.py`
  - [x] `DELETE /extract/{extraction_id}` with `Depends(get_db)`
  - [x] 404 via `JSONResponse` + `ErrorResponse` when doc not found
  - [x] `db.delete(doc)` + `db.commit()` — ORM cascade handles line_items
  - [x] Returns HTTP 200 `DeleteExtractionResponse`

- [x] Task 3: Register the extraction router in `main.py` (AC: 1, 2)
  - [x] Import `extraction` router in `backend/app/main.py`
  - [x] `app.include_router(extraction.router, prefix="/api")`

- [x] Task 4: Write tests (AC: 1, 2)
  - [x] Create `backend/tests/test_story_3_5.py`
  - [x] Test: DELETE with valid unconfirmed `extraction_id` returns 200
  - [x] Test: Deleted document is no longer in DB after DELETE
  - [x] Test: Associated `extracted_line_items` rows are deleted (cascade verified)
  - [x] Test: DELETE with unknown `extraction_id` returns 404 with `error="not_found"`
  - [x] Test: Response body contains `extraction_id`, `deleted=True`, `message` on success

## Dev Notes

### Existing Models — No Changes Needed

`ExtractedDocument` (`app/models/extracted_document.py`) already has:
```python
line_items = relationship(
    "ExtractedLineItem",
    back_populates="document",
    cascade="all, delete-orphan",   # ← ORM cascade handles line_item deletion
)
```

`ExtractedLineItem` also has `ForeignKey("extracted_documents.id", ondelete="CASCADE")` for DB-level cascade safety.

**Cascade works via ORM**: `db.delete(doc)` deletes the document + all its `line_items` in a single transaction. No manual line_item deletion needed.

### New Schema — `app/schemas/extraction.py`

```python
from pydantic import BaseModel


class DeleteExtractionResponse(BaseModel):
    extraction_id: int
    deleted: bool = True
    message: str
```

### Route Implementation — `app/api/routes/extraction.py`

```python
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.extracted_document import ExtractedDocument
from app.schemas.common import ErrorResponse
from app.schemas.extraction import DeleteExtractionResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete("/extract/{extraction_id}", response_model=DeleteExtractionResponse)
def cancel_extraction(
    extraction_id: int,
    db: Session = Depends(get_db),
) -> DeleteExtractionResponse | JSONResponse:
    doc = db.get(ExtractedDocument, extraction_id)
    if doc is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="not_found",
                message=f"Extraction {extraction_id} not found.",
            ).model_dump(),
        )
    db.delete(doc)
    db.commit()
    logger.info("Extraction %d cancelled and deleted.", extraction_id)
    return DeleteExtractionResponse(
        extraction_id=extraction_id,
        deleted=True,
        message="Extraction cancelled and deleted.",
    )
```

**Notes:**
- Route is **synchronous** (`def`, not `async def`) — all DB operations are synchronous SQLAlchemy; no LLM calls
- `db.get(ExtractedDocument, extraction_id)` is the SQLAlchemy 2.x identity-map lookup (equivalent to `SELECT WHERE id = ?`); returns `None` if not found (no exception)
- The 404 response uses `JSONResponse` because FastAPI's `response_model` validation applies only to successful returns; returning `JSONResponse` directly bypasses it for error cases
- The `ErrorResponse` from `app.schemas.common` is reused for the 404 body — consistent with the rest of the API

### Registration in `main.py`

Add after the existing `analytics` router line:
```python
from app.api.routes import analytics, extraction, system
# ...
app.include_router(extraction.router, prefix="/api")
```

The model imports for `ExtractedDocument` and `ExtractedLineItem` are already present in `main.py` (lines 13–14) — no change needed there.

### Scope Boundary — What This Story Does NOT Cover

- Does NOT implement `POST /extract` (Story 3.1)
- Does NOT add a guard for `confirmed_by_user=1` (spec only defines behaviour for unknown IDs, not confirmed ones; leave deletion unrestricted for now — Story 3.4 is the business guard for confirmed records)
- Does NOT need a Verifier pass — this is a delete of an unconfirmed record, not a write of new data

### Test Pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base


def _make_seeded_db():
    """In-memory SQLite with extracted_documents and extracted_line_items tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)   # creates all tables including extracted_documents
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, Factory


def _get_client(factory):
    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

**CRITICAL**: Use `Base.metadata.create_all(engine)` — not a hand-rolled `CREATE TABLE`. `Base` from `app.core.database` already knows about `ExtractedDocument` and `ExtractedLineItem` (their modules are imported in `app.main` before `init_db()` is called). Importing `app.main` in the test file triggers those model imports automatically.

**Seeding test data** — insert a row directly via ORM:
```python
from app.models.extracted_document import ExtractedDocument
from app.models.extracted_line_item import ExtractedLineItem

db = factory()
doc = ExtractedDocument(source_filename="test.pdf", confirmed_by_user=0)
db.add(doc)
db.flush()  # assigns doc.id
item = ExtractedLineItem(document_id=doc.id, description="Widget", quantity=1)
db.add(item)
db.commit()
extraction_id = doc.id
db.close()
```

### Prior Story Learnings (from Stories 2.x)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` BEFORE any `app.*` import
- `StaticPool` for in-memory SQLite so all sessions share the same connection
- `app.dependency_overrides.clear()` in `setup_method` between tests
- `Base.metadata.create_all(engine)` (not hand-rolled DDL) ensures foreign keys and cascades are set up correctly
- The 404 path uses `JSONResponse` directly — `response_model` only applies to successful returns
- `db.get(Model, pk)` is the preferred SQLAlchemy 2.x lookup by primary key

### File List

New files:
- `backend/app/schemas/extraction.py`
- `backend/app/api/routes/extraction.py`
- `backend/tests/test_story_3_5.py`

Modified files:
- `backend/app/main.py` — import `extraction` router and register with `prefix="/api"`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — 7/7 new tests passed on first run; 291/291 total (no regressions).

### Completion Notes List

- Route is synchronous (`def cancel_extraction`) — only SQLAlchemy DB operations, no LLM calls.
- ORM cascade (`cascade="all, delete-orphan"` on `ExtractedDocument.line_items`) handles `extracted_line_items` deletion automatically — no manual cleanup needed.
- 404 path returns `JSONResponse` directly, bypassing `response_model` validation (FastAPI constraint).
- Cascade deletion verified in tests by seeding a line item and confirming it's gone after DELETE.

### File List

- `backend/app/schemas/extraction.py` — `DeleteExtractionResponse`
- `backend/app/api/routes/extraction.py` — `DELETE /extract/{extraction_id}`
- `backend/app/main.py` — import + register extraction router
- `backend/tests/test_story_3_5.py` — 7 tests

### Review Findings

- [x] [Review][Patch] No rollback on `db.commit()` failure in `cancel_extraction` [backend/app/api/routes/extraction.py:28] — no try/except around `db.delete(doc)` + `db.commit()`; an exception leaves the session dirty; `post_confirm` shows the correct pattern with rollback
- [x] [Review][Patch] `engine` variable unused in test helper calls [backend/tests/test_story_3_5.py] — `engine, factory = _make_db()` assigns `engine` but it is never referenced; dead code in every test method

- [x] [Review][Defer] SQLite FK enforcement not enabled in tests [backend/tests/test_story_3_5.py] — deferred, pre-existing pattern across all test files; ORM-level cascade works correctly
- [x] [Review][Defer] No auth/IDOR guard on DELETE endpoint [backend/app/api/routes/extraction.py] — deferred, pre-existing — no auth anywhere in the API; Epic 6/hardening scope
- [x] [Review][Defer] JSONResponse bypasses response_model for 404 error path [backend/app/api/routes/extraction.py:22] — deferred, pre-existing design pattern; spec explicitly uses this approach
- [x] [Review][Defer] `test_endpoint_in_openapi_spec` uses real (non-overridden) TestClient [backend/tests/test_story_3_5.py] — deferred, pre-existing pattern from test_story_3_4.py
- [x] [Review][Defer] `dependency_overrides` not cleared in teardown_method [backend/tests/test_story_3_5.py] — deferred, pre-existing project convention; setup_method handles cleanup
- [x] [Review][Defer] No guard for deleting confirmed extraction (`confirmed_by_user=1`) [backend/app/api/routes/extraction.py] — deferred, spec-intentional: "leave deletion unrestricted for now"
- [x] [Review][Defer] Route at `/api/extract/{id}` outside `/documents` namespace [backend/app/api/routes/extraction.py] — deferred, spec-mandated path; intentional design

## Change Log

- 2026-03-30: Story created by SM agent.
- 2026-03-30: Story 3.5 implemented — cancel/delete endpoint + cascade line_item deletion
