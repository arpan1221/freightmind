# Story 2.5: Schema Endpoint — GET /api/schema

Status: done

## Story

As a developer (and evaluator),
I want a `GET /api/schema` endpoint that exposes all table names, row counts, column names, and sample values,
So that I can inspect what data is available and verify the system loaded correctly.

## Acceptance Criteria

1. **Given** the database is populated with the SCMS dataset
   **When** `GET /api/schema` is called
   **Then** the response returns a JSON object listing each table name, its row count, all column names, and up to 3 sample distinct values per column (FR34)
   **And** the response is read-only — no writes are triggered

2. **Given** the schema endpoint is accessed
   **When** the FastAPI docs at `/docs` are opened
   **Then** the endpoint appears in the auto-generated Swagger UI (FR36)

## Tasks / Subtasks

- [x] Task 1: Create `SchemaInfoResponse` Pydantic schema (AC: 1)
  - [x] Create `backend/app/schemas/schema_info.py`
  - [x] Define `ColumnInfo(BaseModel)` with `column_name: str` and `sample_values: list`
  - [x] Define `TableInfo(BaseModel)` with `table_name: str`, `row_count: int`, `columns: list[ColumnInfo]`
  - [x] Define `SchemaInfoResponse(BaseModel)` with `tables: list[TableInfo]`

- [x] Task 2: Implement `GET /schema` route in `system.py` (AC: 1, 2)
  - [x] Add route to `backend/app/api/routes/system.py` alongside existing `/health` route
  - [x] Signature: `async def get_schema(db: Session = Depends(get_db)) -> SchemaInfoResponse`
  - [x] Iterate `Base.metadata.tables` for table names and columns
  - [x] For each table: query `SELECT COUNT(*) FROM "{table_name}"` for row count
  - [x] For each column: query `SELECT DISTINCT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 3` for sample values
  - [x] Wrap per-column sample query in `try/except` — append `sample_values=[]` on any DB error
  - [x] Return `SchemaInfoResponse(tables=[...])` — no error fields, no writes

- [x] Task 3: Write tests (AC: 1, 2)
  - [x] Create `backend/tests/test_story_2_5.py`
  - [x] Test: `GET /api/schema` returns HTTP 200
  - [x] Test: Response has `tables` key that is a list
  - [x] Test: Each table object has `table_name`, `row_count`, `columns`
  - [x] Test: Each column object has `column_name` and `sample_values` (list)
  - [x] Test: `shipments` table is present in `tables`
  - [x] Test: `row_count` matches the actual number of rows in the in-memory test DB
  - [x] Test: `sample_values` for a seeded column returns the correct distinct values
  - [x] Test: Endpoint appears in OpenAPI spec (`GET /openapi.json` includes `/api/schema`)

### Review Findings

- [x] [Review][Patch] Silent exception handlers in `get_schema` have no logging [backend/app/api/routes/system.py:~65,73] — both `except Exception: row_count = 0` and `except Exception: sample_values = []` silently discard errors; add `logger.debug` consistent with `_count_null_exclusions` pattern in analytics.py

- [x] [Review][Defer] SQL f-string interpolation for identifiers [backend/app/api/routes/system.py:~65,71] — deferred, pre-existing pattern project-wide; ORM-controlled names, double-quote mitigation in place, not user input
- [x] [Review][Defer] No authentication on `/schema` endpoint — deferred, pre-existing; auth is out of scope for this story and not implemented anywhere in the project
- [x] [Review][Defer] `_check_model` and health DB block swallow exceptions without logging root cause [backend/app/api/routes/system.py:~26,42] — deferred, pre-existing health check code not changed by this story
- [x] [Review][Defer] `SessionLocal()` UnboundLocalError risk if constructor raises [backend/app/api/routes/system.py:~35] — deferred, pre-existing health check behavior
- [x] [Review][Defer] `sample_values: list` bare typing (no `list[Any]`) [backend/app/schemas/schema_info.py:5] — deferred, intentionally specified in dev notes for mixed-type columns
- [x] [Review][Defer] `Base.metadata.tables` can enumerate tables not yet migrated during rolling deploys — deferred, inherent to spec-prescribed approach; not fixable without changing architecture
- [x] [Review][Defer] API key sent in Authorization header on every health probe — deferred, pre-existing health check behavior not changed by this story
- [x] [Review][Defer] `setup_method` teardown pattern — deferred, established project convention used across all story tests

## Dev Notes

### File locations — critical, do not deviate

| Action | File |
|--------|------|
| **ADD** route | `backend/app/api/routes/system.py` |
| **CREATE** schema | `backend/app/schemas/schema_info.py` |
| **CREATE** tests | `backend/tests/test_story_2_5.py` |
| **NO CHANGES** | `main.py`, `analytics.py`, `database.py`, any other file |

`system.py` is already registered in `main.py` as:
```python
app.include_router(system.router, prefix="/api")
```
Adding `GET /schema` to `system.py` makes it live at `GET /api/schema` automatically — no `main.py` changes.

### Pydantic schema — `app/schemas/schema_info.py`

```python
from pydantic import BaseModel


class ColumnInfo(BaseModel):
    column_name: str
    sample_values: list  # list of distinct non-null values, up to 3; empty list if none


class TableInfo(BaseModel):
    table_name: str
    row_count: int
    columns: list[ColumnInfo]


class SchemaInfoResponse(BaseModel):
    tables: list[TableInfo]
```

No `error` or `message` fields — this endpoint never partially fails; per-column errors degrade gracefully to `sample_values=[]`.

### Route implementation — `app/api/routes/system.py`

Add these imports at the top of system.py (alongside existing imports):
```python
from sqlalchemy.orm import Session
from app.core.database import Base, get_db
from app.schemas.schema_info import SchemaInfoResponse, TableInfo, ColumnInfo
```

Add the route below the existing health endpoint:
```python
@router.get("/schema", response_model=SchemaInfoResponse)
async def get_schema(db: Session = Depends(get_db)) -> SchemaInfoResponse:
    """Return all table names, row counts, column names, and up to 3 sample values per column."""
    tables = []
    for table_name, table in Base.metadata.tables.items():
        try:
            row_count = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0
        except Exception:
            row_count = 0

        columns = []
        for col in table.columns:
            try:
                result = db.execute(
                    text(
                        f'SELECT DISTINCT "{col.name}" FROM "{table_name}"'
                        f' WHERE "{col.name}" IS NOT NULL LIMIT 3'
                    )
                )
                sample_values = [row[0] for row in result.fetchall()]
            except Exception:
                sample_values = []
            columns.append(ColumnInfo(column_name=col.name, sample_values=sample_values))

        tables.append(TableInfo(table_name=table_name, row_count=row_count, columns=columns))

    return SchemaInfoResponse(tables=tables)
```

**Key patterns:**
- `Depends(get_db)` — not inline `SessionLocal()`. Health check uses inline because it tests connectivity; schema is a normal read.
- Double-quote all table and column names in SQL (matches pattern established in `_count_null_exclusions`).
- `Base.metadata.tables` — fully populated at startup because `main.py` imports all three models (`shipment`, `extracted_document`, `extracted_line_item`) before serving requests.
- No LLM calls, no `ModelClient`, no `settings.analytics_model`.

### Tables exposed (from SQLAlchemy models)

| Table | Key columns (all returned — 32 total for shipments) |
|-------|-----------------------------------------------------|
| `shipments` | `id`, `country`, `shipment_mode`, `product_group`, `vendor`, `freight_cost_usd`, `weight_kg`, ... |
| `extracted_documents` | `id`, `source_filename`, `invoice_number`, `shipment_mode`, `destination_country`, `extraction_confidence`, ... |
| `extracted_line_items` | `id`, `document_id`, `description`, `quantity`, `unit_price`, `total_price`, `confidence` |

`Base.metadata.tables` returns tables in registration order (insertion order, Python 3.7+). No sorting needed.

### Why `Base.metadata.tables` — not raw SQL introspection

`PRAGMA table_list` or `sqlite_master` are SQLite-specific. Using `Base.metadata.tables` keeps the approach DB-agnostic and consistent with the ORM layer. The `col.name` attribute gives the column name as defined in the ORM model (matches the CSV/DB column names exactly).

### `sample_values: list` type — intentional

Typed as bare `list` (not `list[str]`) because columns contain integers, floats, and strings. Pydantic serializes all Python primitives to JSON. No coercion to string is needed; the LLM consumers of this endpoint (and the frontend DatasetStatus card) handle mixed types correctly.

### Swagger visibility (AC2)

Automatic: `@router.get("/schema", response_model=SchemaInfoResponse)` is sufficient for FastAPI to include the route in `/openapi.json` and `/docs`. No additional configuration needed.

### Testing pattern

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


def _make_in_memory_db_with_data():
    """In-memory SQLite seeded with one shipments row for sample value testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Base.metadata.create_all creates all three tables registered in ORM models
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO shipments (
                id, project_code, country, managed_by, fulfill_via, product_group,
                vendor, line_item_quantity, line_item_value, shipment_mode
            ) VALUES (1, 'SC-001', 'Nigeria', 'PMO', 'Direct', 'ARV', 'Acme', 100, 5000.0, 'Air')
        """))
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return Factory


class TestSchemaEndpoint:
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

    def test_returns_200(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        resp = client.get("/api/schema")
        assert resp.status_code == 200

    def test_response_has_tables_list(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        body = client.get("/api/schema").json()
        assert "tables" in body
        assert isinstance(body["tables"], list)

    def test_each_table_has_required_fields(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        tables = client.get("/api/schema").json()["tables"]
        for t in tables:
            assert "table_name" in t
            assert "row_count" in t
            assert "columns" in t
            assert isinstance(t["columns"], list)

    def test_each_column_has_name_and_samples(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        tables = client.get("/api/schema").json()["tables"]
        for t in tables:
            for col in t["columns"]:
                assert "column_name" in col
                assert "sample_values" in col
                assert isinstance(col["sample_values"], list)

    def test_shipments_table_present(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        table_names = [t["table_name"] for t in client.get("/api/schema").json()["tables"]]
        assert "shipments" in table_names

    def test_shipments_row_count_reflects_seeded_data(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        tables = client.get("/api/schema").json()["tables"]
        shipments = next(t for t in tables if t["table_name"] == "shipments")
        assert shipments["row_count"] == 1

    def test_sample_values_returned_for_seeded_column(self):
        factory = _make_in_memory_db_with_data()
        client = self._get_client(factory)
        tables = client.get("/api/schema").json()["tables"]
        shipments = next(t for t in tables if t["table_name"] == "shipments")
        country_col = next(c for c in shipments["columns"] if c["column_name"] == "country")
        assert "Nigeria" in country_col["sample_values"]

    def test_endpoint_in_openapi_spec(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        assert "/api/schema" in spec["paths"]
        assert "get" in spec["paths"]["/api/schema"]
```

**Critical test note:** The in-memory DB test uses `Base.metadata.create_all(engine)` to create the three ORM-registered tables. This requires that all model imports have already run — they have, because `app.main` imports `app.models.*` at module level during `TestClient(app)` construction.

The `INSERT INTO shipments` must supply values for all `NOT NULL` columns: `id`, `project_code`, `country`, `managed_by`, `fulfill_via`, `product_group`, `vendor`, `line_item_quantity`, `line_item_value`. Check `backend/app/models/shipment.py` for the full NOT NULL list.

### Previous story learnings (from Stories 2.1–2.4)

- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` before any `app.*` import in every test file.
- Test class pattern: `class Test<Feature>:` with `setup_method` for dependency override cleanup.
- `TestClient(app)` triggers lifespan startup; model imports run, `Base.metadata` is populated.
- `app.dependency_overrides.clear()` in `setup_method` prevents cross-test leakage.
- `StaticPool` ensures all connections share one in-memory instance — tables created in setup remain visible to test sessions.
- `Depends(get_db)` in routes: override with `app.dependency_overrides[get_db] = override_get_db`.
- The `system.py` health route uses inline `SessionLocal()` — do NOT change that pattern. The schema route uses `Depends(get_db)` since it's not a connectivity probe.
- `settings.analytics_model` is used throughout analytics routes — not needed here (no LLM calls in schema endpoint).
- Double-quote column and table names in all raw SQL: `f'SELECT ... FROM "{table_name}" WHERE "{col}" IS NOT NULL'`.

### What NOT to change

- `backend/app/api/routes/analytics.py` — no changes
- `backend/app/main.py` — no changes
- `backend/app/core/database.py` — no changes
- `backend/app/models/*.py` — no changes
- Any existing test file — no changes

### References

- [Source: epics.md — Story 2.5, FR34]: "System exposes the complete database schema, table row counts, and sample column values via a dedicated read-only endpoint"
- [Source: epics.md — Story 2.5, FR36]: "System auto-generates and exposes interactive API documentation"
- [Source: architecture.md — system.py]: `GET /schema` belongs in `routes/system.py`; schema model in `schemas/schema_info.py`
- [Source: architecture.md — Transparency boundary]: `/api/health` and `/api/schema` are both read-only introspection endpoints; no LLM calls
- [Source: epics.md — Story 2.6 dependency]: `DatasetStatus.tsx` frontend component sources its data from `GET /api/schema`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — clean implementation, all 8 tests passed on first run.

### Completion Notes List

- Created `backend/app/schemas/schema_info.py` with `ColumnInfo`, `TableInfo`, `SchemaInfoResponse` Pydantic models. Used bare `list` (not `list[str]`) for `sample_values` to accommodate mixed column types (int, float, str).
- Added `GET /schema` route to `backend/app/api/routes/system.py` using `Depends(get_db)` (not inline `SessionLocal()`). Route iterates `Base.metadata.tables`, queries row counts and DISTINCT sample values with double-quoted identifiers. Per-column exceptions degrade gracefully to `sample_values=[]`.
- Created `backend/tests/test_story_2_5.py` with 8 tests using `StaticPool` in-memory SQLite seeded with one `shipments` row. Tests cover HTTP 200, response structure, field presence, shipments table presence, row count accuracy, sample value correctness, and OpenAPI spec inclusion.
- Full regression suite: 185 tests passed, 0 failures.

### File List

- `backend/app/schemas/schema_info.py` (created)
- `backend/app/api/routes/system.py` (modified — added imports and GET /schema route)
- `backend/tests/test_story_2_5.py` (created)

## Change Log

- 2026-03-30: Implemented Story 2.5 — GET /api/schema endpoint with Pydantic response models and 8 passing tests
