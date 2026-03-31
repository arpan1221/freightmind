# Story 3.8: Vision extraction standalone invocability

Status: done

## Story

As a developer,
I want to invoke and test the vision extraction agent independently without starting the analytics module,
So that I can develop and debug the extraction pipeline in isolation.

## Acceptance Criteria

1. **Given** only the extraction-related modules are imported
   **When** `POST /api/documents/extract` is called
   **Then** it processes successfully without any import of analytics agent modules (FR42)

2. **Given** the analytics route files are absent
   **When** the extraction agent is invoked directly
   **Then** it runs without import errors

## Tasks / Subtasks

- [x] Task 1: Write isolation test — minimal extraction-only app (AC: 1, 2)
  - [x] Create `backend/tests/test_story_3_8.py`
  - [x] Build a minimal FastAPI app mounting ONLY `documents.router` and `extraction.router` — no analytics router, no `app.main` lifespan
  - [x] Use SQLAlchemy `StaticPool` in-memory DB; raw SQL creates `extracted_documents` + `extracted_line_items` tables (avoids model import order dependency)
  - [x] Override `get_db` dependency with the in-memory session factory
  - [x] Test: `POST /api/documents/extract` with a fake PNG upload returns 200 with correct `ExtractionResponse` shape (has `extraction_id`, `filename`, `fields`, `line_items`)
  - [x] Test: Response `extraction_id` is a positive integer (confirms DB row was inserted)
  - [x] Test: static AST analysis — all 9 extraction module files have zero analytics-related imports

- [x] Task 2: Guard against future cross-module contamination (AC: 1, 2)
  - [x] Add isolation contract comment block to `backend/app/agents/extraction/__init__.py` documenting the FR42 invariant
  - [x] Parametrized AST test covers all 9 extraction module files (3 integration + 9 parametrized = 12 tests total)

### Review Findings

- [x] [Review][Patch] Duplicate parametrize IDs — `ids=lambda p: p.name` generates `documents.py` and `extraction.py` twice (routes vs schemas), pytest disambiguates silently with `0`/`1` suffixes making failure output ambiguous [backend/tests/test_story_3_8.py:223]
- [x] [Review][Patch] Missing NOT NULL on `document_id` in raw extracted_line_items DDL — ORM model has `nullable=False` + FK cascade; test schema omits constraint, silently allowing null FK values [backend/tests/test_story_3_8.py:108]
- [x] [Review][Patch] AST scan misses `from <module> import analytics` pattern — `ImportFrom` handler only checks `node.module`, not alias names in `node.names`; `from app.agents import analytics as al` would pass undetected [backend/tests/test_story_3_8.py:227-237]
- [x] [Review][Defer] Raw SQL schema drift from SQLAlchemy models not detected — pre-existing accepted tradeoff, same pattern as story 2.7 isolation test
- [x] [Review][Defer] `os.environ.setdefault` at module level mutates process env — pre-existing pattern used in every test file in the project
- [x] [Review][Defer] Router prefix asymmetry between documents.router (has `/documents`) and extraction.router (no prefix) — pre-existing design, not introduced by this change
- [x] [Review][Defer] `ModelClient` patched with no spec or return_value — acceptable in isolation test context; mock chain satisfies route without reaching real client; pre-existing pattern

---

## Dev Notes

### Current Module Isolation Status

**Extraction modules already have zero analytics imports.** Verify with:
```bash
grep -rn "analytics" app/agents/extraction/ app/api/routes/documents.py app/api/routes/extraction.py app/schemas/documents.py app/schemas/extraction.py
# → should return no matches
```

The only place analytics modules are loaded is `app/main.py` line 16:
```python
from app.api.routes import analytics, documents, extraction, system
```
Tests for story 3.8 must **NOT** import `app.main` — build a minimal app directly.

---

### Minimal App Pattern

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")  # MUST be before any app.* import

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import only extraction-related routes — NOT analytics
from app.api.routes import documents, extraction
from app.core.database import Base, get_db

# Import extraction models to register them to Base.metadata
import app.models.extracted_document   # noqa: F401
import app.models.extracted_line_item  # noqa: F401
# DO NOT import app.models.shipment here — not needed for extraction


def _make_minimal_extraction_app():
    """FastAPI app with ONLY extraction routers — no analytics."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Creates extracted_documents + extracted_line_items (shipments NOT created — not needed)
    Base.metadata.create_all(engine)
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)

    app = FastAPI()
    app.include_router(documents.router, prefix="/api")   # POST /api/documents/extract etc.
    app.include_router(extraction.router, prefix="/api")  # DELETE /api/extract/{id}

    def override_get_db():
        db = Factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app
```

---

### Mock Pattern for the Extraction Pipeline

The `POST /api/documents/extract` route in `documents.py` calls (in order):
1. `ExtractionPlanner.prepare(file_bytes, content_type)` → `(image_bytes, mime_type)` — static method
2. `ModelClient(timeout=settings.vision_timeout)` — instantiated inside route
3. `ExtractionExecutor(client).extract(image_bytes, mime_type)` → `raw dict` — **async**
4. `ExtractionVerifier().verify(raw)` → `{"fields": ..., "line_items": ..., "low_confidence_fields": [...]}`

Mock all three at `app.api.routes.documents.*` — do NOT mock at the original module path:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.documents import ExtractedField, ExtractedLineItemOut

_HEADER_FIELDS = [
    "invoice_number", "invoice_date", "shipper_name", "consignee_name",
    "origin_country", "destination_country", "shipment_mode", "carrier_vendor",
    "total_weight_kg", "total_freight_cost_usd", "total_insurance_usd",
    "payment_terms", "delivery_date",
]

def _make_fake_verified_result():
    return {
        "fields": {
            f: ExtractedField(value=None if f in {"total_weight_kg", "total_freight_cost_usd", "total_insurance_usd"} else "TEST", confidence="HIGH")
            for f in _HEADER_FIELDS
        },
        "line_items": [],
        "low_confidence_fields": [],
    }


def _make_patches():
    """Context managers to mock the full extraction pipeline."""
    mock_planner = patch(
        "app.api.routes.documents.ExtractionPlanner.prepare",
        return_value=(b"\x89PNG\r\n\x1a\n", "image/png"),  # minimal valid PNG header
    )
    mock_executor_cls = MagicMock()
    mock_executor_instance = mock_executor_cls.return_value
    mock_executor_instance.extract = AsyncMock(return_value={"raw": "data"})

    mock_verifier_cls = MagicMock()
    mock_verifier_cls.return_value.verify.return_value = _make_fake_verified_result()
    mock_verifier_cls.return_value.validate_corrections.return_value = (True, None)

    return (
        mock_planner,
        patch("app.api.routes.documents.ExtractionExecutor", mock_executor_cls),
        patch("app.api.routes.documents.ExtractionVerifier", mock_verifier_cls),
        patch("app.api.routes.documents.ModelClient"),
    )
```

Test using all patches together:
```python
def test_post_extract_returns_200():
    app = _make_minimal_extraction_app()
    client = TestClient(app)

    with _make_patches()[0], _make_patches()[1], _make_patches()[2], _make_patches()[3]:
        # Actually use context manager stacking:
        pass

# Cleaner approach — use ExitStack or nest with statements
import contextlib

def test_post_extract_on_minimal_app_returns_200():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    app = _make_minimal_extraction_app()
    client = TestClient(app)

    mock_executor = MagicMock()
    mock_executor.return_value.extract = AsyncMock(return_value={"raw": "data"})
    mock_verifier = MagicMock()
    mock_verifier.return_value.verify.return_value = _make_fake_verified_result()

    with (
        patch("app.api.routes.documents.ExtractionPlanner.prepare", return_value=(fake_png, "image/png")),
        patch("app.api.routes.documents.ExtractionExecutor", mock_executor),
        patch("app.api.routes.documents.ExtractionVerifier", mock_verifier),
        patch("app.api.routes.documents.ModelClient"),
    ):
        resp = client.post(
            "/api/documents/extract",
            files={"file": ("test.png", fake_png, "image/png")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "extraction_id" in body
    assert "fields" in body
    assert "line_items" in body
    assert body["error"] is None
```

**Important:** Python 3.10+ supports parenthesized `with (...)` syntax for multiple context managers. The codebase uses Python 3.12, so this is safe.

---

### Static AST Analysis — Extraction Module Files to Scan

Scan these 9 files for analytics imports:

```python
import ast
import pathlib

_BACKEND_ROOT = pathlib.Path(__file__).parent.parent

_EXTRACTION_MODULE_PATHS = [
    _BACKEND_ROOT / "app/agents/extraction/__init__.py",
    _BACKEND_ROOT / "app/agents/extraction/planner.py",
    _BACKEND_ROOT / "app/agents/extraction/executor.py",
    _BACKEND_ROOT / "app/agents/extraction/verifier.py",
    _BACKEND_ROOT / "app/agents/extraction/normaliser.py",
    _BACKEND_ROOT / "app/api/routes/documents.py",
    _BACKEND_ROOT / "app/api/routes/extraction.py",
    _BACKEND_ROOT / "app/schemas/documents.py",
    _BACKEND_ROOT / "app/schemas/extraction.py",
]

_ANALYTICS_MARKERS = ("analytics",)  # any import containing this string is a violation
```

AST scan pattern (identical approach to story 2.7):
```python
@pytest.mark.parametrize("filepath", _EXTRACTION_MODULE_PATHS, ids=lambda p: p.name)
def test_extraction_module_has_no_analytics_imports(filepath: pathlib.Path):
    source = filepath.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None) or ""
            for marker in _ANALYTICS_MARKERS:
                assert marker not in module, (
                    f"{filepath.name}: found analytics import: {ast.dump(node)}"
                )
            for alias in getattr(node, "names", []):
                for marker in _ANALYTICS_MARKERS:
                    assert marker not in alias.name, (
                        f"{filepath.name}: found analytics import: {ast.dump(node)}"
                    )
```

---

### Isolation Contract Comment (`extraction/__init__.py`)

The current `extraction/__init__.py` is empty (1 line). Replace with:

```python
# Extraction agent — module isolation contract
# ────────────────────────────────────────────
# This package (app.agents.extraction) and its routes (app.api.routes.documents,
# app.api.routes.extraction) must NEVER import from:
#   - app.agents.analytics
#   - app.api.routes.analytics
#   - app.schemas.analytics
#
# This isolation enables standalone invocability (FR42) and is verified by
# tests/test_story_3_8.py. Violating this contract will break the standalone test.
```

---

### Test Class Structure

```python
class TestExtractionStandaloneApp:
    """Verify extraction routes work on a minimal app with no analytics modules."""

    def test_post_extract_on_minimal_app_returns_200(self): ...
    def test_post_extract_response_shape(self): ...
    def test_post_extract_inserts_db_row(self): ...  # extraction_id > 0


class TestExtractionModuleIsolation:
    """Verify extraction modules have no analytics imports — static AST analysis."""

    @pytest.mark.parametrize("filepath", _EXTRACTION_MODULE_PATHS, ids=lambda p: p.name)
    def test_extraction_module_has_no_analytics_imports(self, filepath): ...
```

---

### Prior Story Learnings (from Story 2.7)

- **CRITICAL:** Set `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` **as the very first line** of the test file, before any `app.*` import — `Settings` is instantiated at import time and will fail without it.
- Use `StaticPool` for in-memory SQLite — ensures all sessions share the same connection and see each other's writes.
- Do **NOT** import `app.main` — it imports analytics + extraction models and includes all routers; this pollutes `sys.modules` and invalidates isolation assertions.
- `app.dependency_overrides.clear()` not needed here (no class-level `TestClient` with shared state), but add `setup_method` cleanup if using class fixtures.
- Static AST analysis is the correct approach (not `sys.modules` assertions) — `sys.modules` is contaminated by other test files that import `app.main`.
- `_BACKEND_ROOT = pathlib.Path(__file__).parent.parent` — anchor all `Path` objects to prevent cwd-relative resolution issues.
- `mock.extract = AsyncMock(...)` — `ExtractionExecutor.extract` is `async def`; must be `AsyncMock` not `MagicMock`.

---

### File Structure

This story creates **ONE new file** and modifies **ONE existing file**:

- `backend/tests/test_story_3_8.py` — **new**: isolation tests (3 integration + 9 AST parametrized = 12 tests)
- `backend/app/agents/extraction/__init__.py` — **modified**: add FR42 isolation contract comment

No new API endpoints. No schema changes. No prompt changes. No frontend changes.

---

### Scope Boundary

Do **NOT**:
- Modify `main.py` — the combined router registration there is intentional
- Create a separate `extraction_main.py` entry point (not required by ACs)
- Add `if __name__ == "__main__"` guards to extraction files (not required)
- Mock at the original module path (e.g., `app.agents.extraction.executor.ExtractionExecutor`) — always mock where the name is looked up: `app.api.routes.documents.ExtractionExecutor`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — extraction modules were already fully isolated from analytics modules. No production code changes required beyond the `__init__.py` comment.

### Completion Notes List

- Created `backend/tests/test_story_3_8.py` with 12 tests across 2 classes:
  - `TestExtractionStandaloneApp` (3 tests): builds a minimal FastAPI app with only `documents.router` + `extraction.router` mounted (no `app.main`, no analytics imports); verifies `POST /api/documents/extract` returns 200 with correct shape and inserts a DB row with `extraction_id > 0`
  - `TestExtractionModuleIsolation` (9 tests, parametrized): static AST analysis of all 9 extraction module files, asserting zero analytics-related imports in each
- Used raw SQL table creation instead of SQLAlchemy model imports for the in-memory DB setup — avoids dependency on model registration order and is consistent with the analytics standalone test (story 2.7) pattern
- Mocked at `app.api.routes.documents.*` (where names are looked up), not at original module paths — required for `patch()` to intercept correctly
- `ExtractionExecutor.extract` is `async def`, mocked with `AsyncMock` — using `MagicMock` here would cause coroutine type errors
- Updated `backend/app/agents/extraction/__init__.py` with FR42 isolation contract comment documenting which analytics modules must never be imported
- 309/309 tests passing, zero regressions

### File List

- `backend/tests/test_story_3_8.py` — new: 12 isolation tests (3 integration + 9 AST static analysis)
- `backend/app/agents/extraction/__init__.py` — modified: added FR42 isolation contract comment

## Change Log

- 2026-03-30: Story created by SM agent.
- 2026-03-30: Implemented by dev agent (claude-sonnet-4-6). 12 new tests, 309/309 passing. Status: review.
