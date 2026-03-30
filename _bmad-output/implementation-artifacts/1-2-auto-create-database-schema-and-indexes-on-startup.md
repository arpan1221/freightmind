# Story 1.2: Auto-create database schema and indexes on startup

Status: done

## Story

As a developer,
I want all required SQLite tables and indexes created automatically when the backend starts,
So that no manual migration step is needed on a fresh deploy.

## Acceptance Criteria

1. **Given** the backend starts against a fresh SQLite file (no existing tables),
   **When** the startup lifespan event fires,
   **Then** `shipments`, `extracted_documents`, and `extracted_line_items` tables are created with all columns matching the architecture schema
   **And** indexes are created on `shipments.country`, `shipments.shipment_mode`, `shipments.vendor`, `shipments.product_group`, `shipments.scheduled_delivery_date`, `extracted_documents.destination_country`, and `extracted_documents.shipment_mode`
   **And** the operation completes without error

2. **Given** the backend restarts against an existing SQLite file with tables already present,
   **When** the startup lifespan event fires,
   **Then** no error is raised and no duplicate tables or indexes are created (SQLAlchemy `create_all` with `checkfirst=True` behaviour — no-op if exists)

3. **Given** the database engine is initialised,
   **When** `get_db()` is called as a FastAPI dependency,
   **Then** it yields a `Session` and closes it after the request completes

## Tasks / Subtasks

- [x] Task 1: Create `backend/app/core/database.py` (AC: 1, 2, 3)
  - [x] Import `create_engine`, `sessionmaker`, `declarative_base` from SQLAlchemy 2.x
  - [x] Create engine from `settings.database_url` with `connect_args={"check_same_thread": False}` for SQLite
  - [x] Create `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`
  - [x] Create `Base = declarative_base()`
  - [x] Implement `init_db()` → calls `Base.metadata.create_all(bind=engine)` — idempotent
  - [x] Implement `get_db()` FastAPI dependency (generator: yield session, close in finally)

- [x] Task 2: Create `Shipment` ORM model (AC: 1, 2)
  - [x] Create `backend/app/models/shipment.py`
  - [x] Define `Shipment` class inheriting from `Base`; `__tablename__ = "shipments"`
  - [x] Map all 33 columns exactly as specified in Dev Notes (column types and nullability)
  - [x] Define `__table_args__` with all 5 shipments indexes (see Dev Notes)

- [x] Task 3: Create `ExtractedDocument` ORM model (AC: 1, 2)
  - [x] Create `backend/app/models/extracted_document.py`
  - [x] Define `ExtractedDocument` class; `__tablename__ = "extracted_documents"`
  - [x] Map all 18 columns with correct types, defaults (`confirmed_by_user=0`, `extracted_at=func.now()`)
  - [x] Define `__table_args__` with 2 extracted_documents indexes
  - [x] Define relationship to `ExtractedLineItem` (cascade delete)

- [x] Task 4: Create `ExtractedLineItem` ORM model (AC: 1, 2)
  - [x] Create `backend/app/models/extracted_line_item.py`
  - [x] Define `ExtractedLineItem` class; `__tablename__ = "extracted_line_items"`
  - [x] Map all 7 columns; FK `document_id → extracted_documents.id` with `ondelete="CASCADE"`

- [x] Task 5: Wire `init_db()` into lifespan hook (AC: 1, 2)
  - [x] In `backend/app/main.py`, import `init_db` from `app.core.database`
  - [x] Import all models before `init_db()` call so SQLAlchemy registers them on `Base.metadata`
  - [x] Call `init_db()` inside the `lifespan` async context manager before `yield`

- [x] Task 6: Write tests (AC: 1, 2, 3)
  - [x] Use a temp SQLite file (or `:memory:`) per test — never the production DB
  - [x] Test: fresh DB → all 3 tables exist after `init_db()`
  - [x] Test: restart → `init_db()` called twice raises no error
  - [x] Test: all required indexes exist on `shipments` and `extracted_documents`
  - [x] Test: `get_db()` yields a session and closes it
  - [x] Test: `Shipment`, `ExtractedDocument`, `ExtractedLineItem` can be inserted and queried

## Dev Notes

### `app/core/database.py` — Canonical Implementation

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create all tables and indexes. No-op if they already exist."""
    # Models must be imported before this call so Base.metadata knows about them.
    # Imports happen in app/main.py before init_db() is called.
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and guarantees close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Critical:** `connect_args={"check_same_thread": False}` is **required** for SQLite when used with FastAPI async routes — without it, SQLite raises `SQLite objects created in a thread can only be used in that same thread`.

### `app/main.py` — Updated Lifespan

```python
from contextlib import asynccontextmanager
from app.core.database import init_db
# IMPORTANT: import models BEFORE calling init_db() so Base.metadata registers them
import app.models.shipment  # noqa: F401
import app.models.extracted_document  # noqa: F401
import app.models.extracted_line_item  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Story 1.2: create tables + indexes
    # Story 1.3 will add CSV load here
    yield
```

**Why import models before `init_db()`?** SQLAlchemy's `Base.metadata.create_all()` only creates tables it knows about. Models register themselves on `Base.metadata` at import time. If not imported, tables will not be created even though the model files exist.

### `app/models/shipment.py` — Complete ORM Model

```python
from sqlalchemy import Column, Integer, Text, Float, Index
from app.core.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)  # CSV id — NOT autoincrement
    project_code = Column(Text, nullable=False)
    pq_number = Column(Text)
    po_so_number = Column(Text)
    asn_dn_number = Column(Text)
    country = Column(Text, nullable=False)
    managed_by = Column(Text, nullable=False)
    fulfill_via = Column(Text, nullable=False)
    vendor_inco_term = Column(Text)
    shipment_mode = Column(Text, nullable=False)
    pq_first_sent_to_client_date = Column(Text)
    po_sent_to_vendor_date = Column(Text)
    scheduled_delivery_date = Column(Text)
    delivered_to_client_date = Column(Text)
    delivery_recorded_date = Column(Text)
    product_group = Column(Text, nullable=False)
    sub_classification = Column(Text)
    vendor = Column(Text, nullable=False)
    item_description = Column(Text)
    molecule_test_type = Column(Text)
    brand = Column(Text)
    dosage = Column(Text)
    dosage_form = Column(Text)
    unit_of_measure_per_pack = Column(Integer)
    line_item_quantity = Column(Integer, nullable=False)
    line_item_value = Column(Float, nullable=False)
    pack_price = Column(Float)
    unit_price = Column(Float)
    manufacturing_site = Column(Text)
    first_line_designation = Column(Text)
    weight_kg = Column(Float)         # NULL after cleaning non-numeric values
    freight_cost_usd = Column(Float)  # NULL after cleaning non-numeric values
    line_item_insurance_usd = Column(Float)

    __table_args__ = (
        Index("idx_shipments_country", "country"),
        Index("idx_shipments_shipment_mode", "shipment_mode"),
        Index("idx_shipments_vendor", "vendor"),
        Index("idx_shipments_product_group", "product_group"),
        Index("idx_shipments_scheduled_delivery", "scheduled_delivery_date"),
    )
```

**Why `id` is NOT `autoincrement`:** The CSV dataset has its own integer IDs (1–10,324). Story 1.3 will insert them directly from the CSV. Do not let SQLite auto-assign IDs or the CSV IDs will be ignored.

**Why `Text` not `String`:** SQLite's `TEXT` affinity maps to SQLAlchemy `Text`. Using `String` (which maps to `VARCHAR`) also works but `Text` is idiomatic for unbounded columns in SQLite.

**Why `Float` for `weight_kg` / `freight_cost_usd` (nullable):** These columns contain non-numeric strings in the raw CSV (`"Weight Captured Separately"`, `"Invoiced Separately"`). Story 1.3 will clean them to `NULL` during load. The ORM model stores the cleaned value.

### `app/models/extracted_document.py` — Complete ORM Model

```python
from sqlalchemy import Column, Integer, Text, Float, Index, func
from sqlalchemy.orm import relationship
from app.core.database import Base


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
    extracted_at = Column(Text, server_default=func.now())
    confirmed_by_user = Column(Integer, default=0)

    line_items = relationship(
        "ExtractedLineItem",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_extracted_destination", "destination_country"),
        Index("idx_extracted_shipment_mode", "shipment_mode"),
    )
```

**`confirmed_by_user=0` (default):** This flag is the key to the extraction confirm/cancel flow (Story 3.4/3.5). Row is inserted at `POST /extract` with `confirmed_by_user=0`. Analytics linkage queries (Epic 4) filter on `confirmed_by_user=1`. `POST /confirm` flips it to 1.

**`extracted_at` with `server_default=func.now()`:** SQLite's `datetime('now')` is UTC. Using `server_default` means the DB fills it in — not the application layer.

### `app/models/extracted_line_item.py` — Complete ORM Model

```python
from sqlalchemy import Column, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ExtractedLineItem(Base):
    __tablename__ = "extracted_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("extracted_documents.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text)
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_price = Column(Float)
    confidence = Column(Float)

    document = relationship("ExtractedDocument", back_populates="line_items")
```

**`ondelete="CASCADE"`:** When an `ExtractedDocument` is deleted (user cancels extraction — Story 3.5), its line items must also be deleted. Both ORM `cascade="all, delete-orphan"` on `ExtractedDocument.line_items` AND `ForeignKey(..., ondelete="CASCADE")` are needed — ORM cascade handles Python-layer deletes; FK cascade handles direct SQL deletes.

### Test Pattern — Isolated In-Memory DB

```python
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, init_db

@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Import models to register them on Base.metadata
    import app.models.shipment  # noqa
    import app.models.extracted_document  # noqa
    import app.models.extracted_line_item  # noqa
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()
```

**Why `:memory:` not a temp file?** In-memory SQLite is faster, auto-cleaned, and avoids file system side effects. The `test_engine` fixture creates a fresh schema per test; no teardown needed beyond `drop_all`.

**Do NOT use `from app.core.database import engine`** in tests — that binds to the production `settings.database_url`. Always create a test-local engine with `sqlite:///:memory:`.

### Scope Boundary — What NOT to Implement

| Concern | Belongs To |
|---------|-----------|
| CSV loading into `shipments` | Story 1.3 |
| `GET /api/health` DB ping | Story 1.4 |
| Alembic migrations | Never — `create_all` is the pattern for this POC |
| Any analytics or extraction logic | Epics 2–3 |
| `get_db()` used in a real route | Story 1.4 onwards |

**Do NOT** call `session.execute(text("CREATE TABLE ..."))` manually — this is the architecture red flag. Only `Base.metadata.create_all()` is allowed for schema management.

### SQLAlchemy 2.x Notes

- `declarative_base()` is now in `sqlalchemy.orm` (was `sqlalchemy.ext.declarative` in 1.x)
- `sessionmaker` is still in `sqlalchemy.orm`
- `create_engine` is still in `sqlalchemy`
- `Column`, `Integer`, `Text`, `Float`, `Index`, `ForeignKey` all in `sqlalchemy`
- `func` is in `sqlalchemy`

### Architecture Enforcement (from architecture.md)

- All DB setup MUST be in `app/core/database.py` — not scattered in models or routes
- ORM model classes: `PascalCase`, singular (`Shipment`, not `Shipments`)
- Table names: `snake_case`, plural (`shipments`, `extracted_documents`, `extracted_line_items`)
- No `CREATE TABLE` SQL strings anywhere — only `Base.metadata.create_all()`
- `get_db()` dependency is injected via `Depends(get_db)` in route functions — never instantiate `SessionLocal` directly in routes

### Previous Story (1.1) Learnings

- `settings.database_url` defaults to `"sqlite:///./freightmind.db"` — this is where the DB file will be created (relative to the CWD where uvicorn is launched, i.e., `/app/` inside Docker)
- Lifespan hook in `main.py` currently has empty `yield` — this story populates it with `init_db()`
- Router is registered with `prefix="/api"` — `get_db()` will be used in routes following this pattern
- Tests use `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` at top of test file — follow same pattern for test files in this story

### File List (new files after this story)

- `backend/app/core/database.py`
- `backend/app/models/shipment.py`
- `backend/app/models/extracted_document.py`
- `backend/app/models/extracted_line_item.py`
- `backend/tests/test_story_1_2.py`

**Modified files:**
- `backend/app/main.py` (lifespan hook update)
- `backend/app/models/__init__.py` (optional: re-export models for convenience)

### References

- [Source: DATASET_SCHEMA.md] — authoritative column specs for all 3 tables, index definitions
- [Source: architecture.md#Data Architecture] — SQLAlchemy hybrid pattern, `create_all` idempotency, startup sequence
- [Source: architecture.md#Startup Idempotency Pattern] — `Base.metadata.create_all` vs raw CREATE TABLE
- [Source: architecture.md#Database & ORM naming] — table names, class names
- [Source: epics.md#Story 1.2] — acceptance criteria
- [Source: architecture.md#Gap 1] — `confirmed_by_user=0` default on insert

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- **`session.is_active` in SQLAlchemy 2.x:** After `session.close()`, `is_active` remains `True` — it tracks rolled-back state, not connection state. Replaced assertion with monkeypatched close-call tracking.
- **Pydantic `class Config` deprecation warning:** `Settings` in `core/config.py` uses the old class-based config style (Pydantic v1 pattern). Raises `PydanticDeprecatedSince20` warning at import. Not fixed in this story — belongs to a config cleanup task.

### Completion Notes List

- `app/core/database.py` created: SQLAlchemy engine from `settings.database_url`, `SessionLocal`, `Base`, `init_db()`, `get_db()` dependency. `check_same_thread=False` set for SQLite async safety.
- `app/models/shipment.py`: `Shipment` ORM model, 33 columns, `id` not autoincrement (CSV IDs used directly), 5 indexes in `__table_args__`.
- `app/models/extracted_document.py`: `ExtractedDocument` ORM model, 18 columns, `confirmed_by_user=0` default, `extracted_at` via `server_default=func.now()`, cascade relationship to `ExtractedLineItem`, 2 indexes.
- `app/models/extracted_line_item.py`: `ExtractedLineItem` ORM model, 7 columns, FK with `ondelete="CASCADE"`.
- `app/main.py` lifespan updated: model imports + `init_db()` call before `yield`. Story 1.3 CSV load placeholder comment added.
- 15 tests written covering all ACs (table creation, index existence, idempotency, `get_db()` session close, ORM round-trips, cascade delete, FK constraint). All 15 pass. 26 total (including Story 1.1 regressions) — all pass. Ruff lint clean.

### File List

- `backend/app/core/database.py`
- `backend/app/models/shipment.py`
- `backend/app/models/extracted_document.py`
- `backend/app/models/extracted_line_item.py`
- `backend/tests/test_story_1_2.py`
- `backend/app/main.py` (lifespan hook updated)

### Review Findings

- [x] [Review][Patch] `func.now()` generates invalid SQL for SQLite — fixed: `server_default=text("(datetime('now'))")`. [backend/app/models/extracted_document.py:26]
- [x] [Review][Patch] `confirmed_by_user` missing `server_default="0"` — fixed: added `server_default="0"` alongside Python `default=0`. [backend/app/models/extracted_document.py:27]
- [x] [Review][Patch] `Base.metadata.create_all(bind=engine)` uses deprecated SQLAlchemy 2.x API — fixed: `with engine.begin() as conn: Base.metadata.create_all(conn)`. [backend/app/core/database.py:23]
- [x] [Review][Patch] `sessionmaker(bind=engine)` uses deprecated `bind=` parameter — fixed: `sessionmaker(engine, ...)`. [backend/app/core/database.py:15]
- [x] [Review][Patch] `Base.metadata.drop_all(bind=mem_engine)` in test fixture uses deprecated API — fixed: `with engine.begin() as conn: Base.metadata.drop_all(conn)`. [backend/tests/test_story_1_2.py:35]
- [x] [Review][Defer] Side-effect model imports in `main.py` are fragile — new models must be manually imported or tables won't be created; consider a model registry pattern in a later story. [backend/app/main.py:10-12] — deferred, pre-existing
- [x] [Review][Defer] `engine` module-level instantiation with relative SQLite path — `./freightmind.db` is CWD-relative; works correctly in Docker but can misbehave in local dev. [backend/app/core/database.py:10] — deferred, pre-existing
- [x] [Review][Defer] `test_foreign_key_constraint_enforced` FK PRAGMA scope — may be fragile with SQLAlchemy 2.x connection pooling resetting PRAGMA state. [backend/tests/test_story_1_2.py:221] — deferred, pre-existing

## Change Log

- 2026-03-30: Story 1.2 created by create-story workflow
- 2026-03-30: Story 1.2 implemented — SQLAlchemy database.py, 3 ORM models, lifespan wired, 15 tests passing
- 2026-03-30: Code review — 0 decision-needed, 5 patches, 3 deferred, 2 dismissed.
