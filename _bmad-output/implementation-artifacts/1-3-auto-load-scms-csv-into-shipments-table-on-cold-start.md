# Story 1.3: Auto-load SCMS CSV into shipments table on cold start

Status: done

## Story

As a logistics analyst,
I want 10,324 shipment records from the SCMS dataset available immediately after the system starts,
So that I can query historical freight data without any manual data import step.

## Acceptance Criteria

1. **Given** the `shipments` table is empty AND `backend/data/SCMS_Delivery_History_Dataset.csv` is present,
   **When** the startup lifespan event fires (after `init_db()` from Story 1.2),
   **Then** all ~10,324 rows are bulk-loaded into the `shipments` table
   **And** `weight_kg` and `freight_cost_usd` columns contain `NULL` for rows where the CSV value is non-numeric (e.g., `"Weight Captured Separately"`, `"Freight Included in Commodity Cost"`)
   **And** all five date columns are stored as ISO `YYYY-MM-DD` text, or `NULL` if unparseable
   **And** the load completes within 60 seconds (NFR12)

2. **Given** the `shipments` table already contains rows,
   **When** the startup lifespan event fires,
   **Then** zero additional rows are inserted (idempotent — count unchanged, load skipped entirely)

3. **Given** `backend/data/SCMS_Delivery_History_Dataset.csv` is absent,
   **When** the startup lifespan event fires,
   **Then** a `FileNotFoundError` is raised with the absolute path of the missing file and the server fails fast

## Tasks / Subtasks

- [x] Task 1: Commit SCMS CSV to repository (AC: 1)
  - [x] Download the SCMS dataset from Kaggle: https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data
  - [x] Place at `backend/data/SCMS_Delivery_History_Dataset.csv` (do NOT rename — use exact Kaggle filename)
  - [x] Verify: `python -c "import pandas as pd; print(len(pd.read_csv('backend/data/SCMS_Delivery_History_Dataset.csv')))"` → must print ~10324

- [x] Task 2: Create `backend/app/core/csv_loader.py` (AC: 1, 2, 3)
  - [x] Define `COLUMN_MAP` dict (33 entries — CSV header → ORM field name, see Dev Notes)
  - [x] Define `DATE_COLS` list (5 date column names in original CSV header format)
  - [x] Define `CSV_PATH = Path(__file__).parent.parent.parent / "data" / "SCMS_Delivery_History_Dataset.csv"`
  - [x] Implement `load_shipments_from_csv(session: Session, csv_path: Path = CSV_PATH) -> int`
  - [x] Idempotency guard: `if session.query(Shipment).count() > 0: return 0`
  - [x] File guard: `if not csv_path.exists(): raise FileNotFoundError(f"SCMS CSV not found at: {csv_path.resolve()}")`
  - [x] Load with `pd.read_csv(csv_path, encoding="utf-8-sig")`
  - [x] Clean numeric sentinels BEFORE rename: `pd.to_numeric(df["Weight (Kilograms)"], errors="coerce")` and same for `"Freight Cost (USD)"`
  - [x] Parse date cols BEFORE rename: `pd.to_datetime(df[col], errors="coerce", format="mixed")` → `.dt.strftime("%Y-%m-%d")` guarded by `.where(parsed.notna(), None)`
  - [x] Strip whitespace: all string/object-dtype columns via `df[col].str.strip()`
  - [x] Rename: `df = df.rename(columns=COLUMN_MAP)`
  - [x] Null-coerce: `df.where()` + explicit `_none_if_nan()` pass on each record (pandas 3.x NaN safety)
  - [x] Bulk insert: `session.execute(insert(Shipment), records)`
  - [x] Commit and return `len(records)`

- [x] Task 3: Update `backend/app/main.py` lifespan (AC: 1, 2, 3)
  - [x] Import `load_shipments_from_csv`, `CSV_PATH` from `app.core.csv_loader`
  - [x] Import `SessionLocal` from `app.core.database`
  - [x] After `init_db()`, create `db = SessionLocal()`, call `load_shipments_from_csv(db, CSV_PATH)` in try/finally
  - [x] Wrap entire startup sequence in try/except — log error and re-raise
  - [x] Remove `# Story 1.3 will add CSV load here` comment

- [x] Task 4: Write tests (AC: 1, 2, 3)
  - [x] Create `backend/tests/test_story_1_3.py`
  - [x] `pytest fixture test_csv(tmp_path)`: synthetic 3-row CSV — row 2 has `"Weight Captured Separately"` and `"Freight Included in Commodity Cost"`, row 1 has non-ISO dates
  - [x] `pytest fixture test_session(tmp_path)`: file SQLite, `Base.metadata.create_all`, imports all models
  - [x] Test AC1a: empty table + valid CSV → row count matches CSV row count
  - [x] Test AC1b: `weight_kg` is `None` for sentinel row; `freight_cost_usd` is `None` for sentinel row
  - [x] Test AC1c: a date column contains ISO string (`YYYY-MM-DD`) for parseable values
  - [x] Test AC2: load twice → second call returns 0, total count = first count (no duplicates)
  - [x] Test AC3: missing CSV path → `FileNotFoundError` with path in message
  - [x] Test: whitespace-padded string in fixture → stored value is stripped

## Dev Notes

### Dependency on Story 1.2

This story requires that Story 1.2 has been implemented first. The following must already exist:
- `backend/app/core/database.py` — `Base`, `SessionLocal`, `init_db()`, `engine`
- `backend/app/models/shipment.py` — `Shipment` ORM model with all 33 columns
- `init_db()` already called in lifespan (added by Story 1.2 task 5)

The current `main.py` already has `init_db()` wired in — do NOT add it again. Story 1.3 adds the CSV load call **after** the existing `init_db()`.

### Column Rename Mapping

Apply as one `df.rename(columns=COLUMN_MAP)` call **after** all cleaning that references original CSV headers:

```python
COLUMN_MAP = {
    "id": "id",
    "Project Code": "project_code",
    "PQ #": "pq_number",
    "PO / SO #": "po_so_number",
    "ASN/DN #": "asn_dn_number",
    "Country": "country",
    "Managed By": "managed_by",
    "Fulfill Via": "fulfill_via",
    "Vendor INCO Term": "vendor_inco_term",
    "Shipment Mode": "shipment_mode",
    "PQ First Sent to Client Date": "pq_first_sent_to_client_date",
    "PO Sent to Vendor Date": "po_sent_to_vendor_date",
    "Scheduled Delivery Date": "scheduled_delivery_date",
    "Delivered to Client Date": "delivered_to_client_date",
    "Delivery Recorded Date": "delivery_recorded_date",
    "Product Group": "product_group",
    "Sub Classification": "sub_classification",
    "Vendor": "vendor",
    "Item Description": "item_description",
    "Molecule/Test Type": "molecule_test_type",
    "Brand": "brand",
    "Dosage": "dosage",
    "Dosage Form": "dosage_form",
    "Unit of Measure (Per Pack)": "unit_of_measure_per_pack",
    "Line Item Quantity": "line_item_quantity",
    "Line Item Value": "line_item_value",
    "Pack Price": "pack_price",
    "Unit Price": "unit_price",
    "Manufacturing Site": "manufacturing_site",
    "First Line Designation": "first_line_designation",
    "Weight (Kilograms)": "weight_kg",
    "Freight Cost (USD)": "freight_cost_usd",
    "Line Item Insurance (USD)": "line_item_insurance_usd",
}
```

**Critical ordering rule:** Clean numeric and date columns using **original** CSV header names, then rename, then NaN→None. Reversing this order breaks the cleaning step because the original column names no longer exist.

### Date Column Handling

```python
DATE_COLS = [
    "PQ First Sent to Client Date",
    "PO Sent to Vendor Date",
    "Scheduled Delivery Date",
    "Delivered to Client Date",
    "Delivery Recorded Date",
]

for col in DATE_COLS:
    parsed = pd.to_datetime(df[col], errors="coerce")  # NaT for bad/empty values
    # strftime on NaT produces "NaT" string in some pandas versions — guard with .where()
    df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)
```

### CSV Path Resolution in Docker vs Local

```
csv_loader.py location:
  Local:  backend/app/core/csv_loader.py
  Docker: /app/app/core/csv_loader.py

Path(__file__).parent.parent.parent resolves to:
  Local:  backend/
  Docker: /app/

So CSV_PATH = Path(__file__).parent.parent.parent / "data" / "SCMS_Delivery_History_Dataset.csv"
  Local:  backend/data/SCMS_Delivery_History_Dataset.csv  ✓
  Docker: /app/data/SCMS_Delivery_History_Dataset.csv     ✓
```

Architecture docs use `scms_shipments.csv` — that is a simplified name from planning. The **actual Kaggle filename** is `SCMS_Delivery_History_Dataset.csv` and that is the name committed to repo.

### Canonical `csv_loader.py`

```python
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent.parent / "data" / "SCMS_Delivery_History_Dataset.csv"

COLUMN_MAP = { ... }  # full dict above

DATE_COLS = [ ... ]  # 5 columns above


def load_shipments_from_csv(session: Session, csv_path: Path = CSV_PATH) -> int:
    """Load SCMS CSV into `shipments` table. Idempotent — skips if rows exist.

    Returns number of rows inserted (0 if skipped).
    Raises FileNotFoundError if csv_path does not exist.
    """
    from app.models.shipment import Shipment  # late import avoids circular at module level

    if session.query(Shipment).count() > 0:
        logger.info("Shipments table already populated — CSV load skipped")
        return 0

    if not csv_path.exists():
        raise FileNotFoundError(f"SCMS CSV not found at: {csv_path.resolve()}")

    logger.info("Loading shipments from %s ...", csv_path)
    df = pd.read_csv(csv_path)

    # Clean sentinel numeric values BEFORE rename
    for col in ["Weight (Kilograms)", "Freight Cost (USD)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse dates to ISO TEXT BEFORE rename
    for col in DATE_COLS:
        parsed = pd.to_datetime(df[col], errors="coerce")
        df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)

    # Strip whitespace from all string columns BEFORE rename
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Rename to ORM column names
    df = df.rename(columns=COLUMN_MAP)

    # Convert ALL NaN / NaT → Python None → SQLite NULL
    df = df.where(pd.notna(df), None)

    records = df.to_dict(orient="records")
    session.execute(insert(Shipment), records)
    session.commit()

    logger.info("Loaded %d shipments", len(records))
    return len(records)
```

### Updated Lifespan in `main.py`

Add after the existing `init_db()` call:

```python
from app.core.csv_loader import load_shipments_from_csv, CSV_PATH
from app.core.database import init_db, SessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()  # Story 1.2: idempotent table + index creation
        db = SessionLocal()
        try:
            load_shipments_from_csv(db, CSV_PATH)  # Story 1.3: seed on cold start
        finally:
            db.close()
    except FileNotFoundError:
        logger.error("CSV file missing at startup — check backend/data/ directory")
        raise
    except Exception as exc:
        logger.error("Startup sequence failed: %s", exc)
        raise
    yield
```

This addresses the deferred-work item: "No lifespan error handling — relevant when DB init and CSV load are added in Stories 1.2/1.3."

### Test Fixture — Synthetic CSV

Never use the real 10K-row CSV in unit tests. Use `tmp_path` to create a small fixture CSV:

```python
import io, os
from pathlib import Path
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")


@pytest.fixture
def test_csv(tmp_path) -> Path:
    rows = [
        {
            "id": 1, "Project Code": "SC-003", "PQ #": "", "PO / SO #": "",
            "ASN/DN #": "", "Country": " Nigeria ", "Managed By": "PMO - US",
            "Fulfill Via": "Direct Drop", "Vendor INCO Term": "EXW",
            "Shipment Mode": "Air",
            "PQ First Sent to Client Date": "3/14/13",  # non-ISO → should parse
            "PO Sent to Vendor Date": "4/3/13",
            "Scheduled Delivery Date": "6/11/13",
            "Delivered to Client Date": "6/19/13",
            "Delivery Recorded Date": "6/19/13",
            "Product Group": "ARV", "Sub Classification": "Adult",
            "Vendor": "ABBVIE", "Item Description": "Lopinavir 200mg",
            "Molecule/Test Type": "Lopinavir", "Brand": "", "Dosage": "200mg",
            "Dosage Form": "Tablet", "Unit of Measure (Per Pack)": 120,
            "Line Item Quantity": 1200, "Line Item Value": 18000.0,
            "Pack Price": 15.0, "Unit Price": 0.125,
            "Manufacturing Site": "Abbvie Inc.", "First Line Designation": "Yes",
            "Weight (Kilograms)": 1500.0, "Freight Cost (USD)": 5765.40,
            "Line Item Insurance (USD)": 120.0,
        },
        {
            "id": 2, "Project Code": "SC-003", "PQ #": None, "PO / SO #": None,
            "ASN/DN #": None, "Country": "Zambia", "Managed By": "SCMS",
            "Fulfill Via": "Direct Drop", "Vendor INCO Term": "FCA",
            "Shipment Mode": "Ocean",
            "PQ First Sent to Client Date": None, "PO Sent to Vendor Date": "6/1/13",
            "Scheduled Delivery Date": "9/1/13", "Delivered to Client Date": None,
            "Delivery Recorded Date": None,
            "Product Group": "HRDT", "Sub Classification": "HIV test",
            "Vendor": "CHEMBIO", "Item Description": "HIV test kit",
            "Molecule/Test Type": "HIV test", "Brand": "Sure Check",
            "Dosage": None, "Dosage Form": "Test Kit",
            "Unit of Measure (Per Pack)": 20, "Line Item Quantity": 5000,
            "Line Item Value": 22500.0, "Pack Price": 4.5, "Unit Price": 0.225,
            "Manufacturing Site": "Chembio", "First Line Designation": "No",
            "Weight (Kilograms)": "Weight Captured Separately",   # sentinel → NULL
            "Freight Cost (USD)": "Freight Included in Commodity Cost",  # sentinel → NULL
            "Line Item Insurance (USD)": None,
        },
        {
            "id": 3, "Project Code": "SC-004", "PQ #": None, "PO / SO #": None,
            "ASN/DN #": None, "Country": "Kenya", "Managed By": "PMO - US",
            "Fulfill Via": "From RDC", "Vendor INCO Term": None, "Shipment Mode": "Truck",
            "PQ First Sent to Client Date": None, "PO Sent to Vendor Date": "2014-01-01",
            "Scheduled Delivery Date": "2014-03-01", "Delivered to Client Date": None,
            "Delivery Recorded Date": None, "Product Group": "ANTM",
            "Sub Classification": None, "Vendor": "CIPLA", "Item Description": None,
            "Molecule/Test Type": None, "Brand": None, "Dosage": None, "Dosage Form": None,
            "Unit of Measure (Per Pack)": None, "Line Item Quantity": 200,
            "Line Item Value": 800.0, "Pack Price": None, "Unit Price": None,
            "Manufacturing Site": None, "First Line Designation": None,
            "Weight (Kilograms)": 45.0, "Freight Cost (USD)": 320.0,
            "Line Item Insurance (USD)": 8.0,
        },
    ]
    csv_path = tmp_path / "SCMS_Delivery_History_Dataset.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def test_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    import app.models.shipment  # noqa — register on Base.metadata
    import app.models.extracted_document  # noqa
    import app.models.extracted_line_item  # noqa
    from app.core.database import Base
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
```

### Sentinel Value Clarification

The **epics file** mentions `"sentinel values (-49)"` — this is inaccurate. The **actual CSV** contains text strings:
- `Weight (Kilograms)`: `"Weight Captured Separately"` → clean to `NULL`
- `Freight Cost (USD)`: `"Freight Included in Commodity Cost"`, `"Invoiced Separately"` → clean to `NULL`

Authority: `DATASET_SCHEMA.md` (directly inspects Kaggle dataset) and `architecture.md` ("NULL coercion"). Use `pd.to_numeric(..., errors="coerce")` — do NOT filter for -49.

### SQLAlchemy 2.x Bulk Insert

Use the 2.x-idiomatic pattern:
```python
from sqlalchemy import insert
session.execute(insert(Shipment), records)  # records = list[dict]
session.commit()
```

Do **not** use `session.bulk_insert_mappings()` — deprecated in SQLAlchemy 2.x. Do **not** use `df.to_sql()` with the engine — using the session keeps all DB access through the session lifecycle managed in main.py.

### Performance

10,324 rows with one `session.execute(insert(...), records)` completes in < 3s locally. No chunking needed. The 60-second NFR12 limit is for cold Render deploy including container startup — CSV insert is not the bottleneck.

### Scope Boundary

| Concern | Belongs To |
|---------|-----------|
| `Shipment` ORM model definition | Story 1.2 |
| `init_db()` / `Base.metadata.create_all()` | Story 1.2 |
| Full health check endpoint | Story 1.4 |
| `extracted_documents` / `extracted_line_items` population | Epic 3 |
| Analytics queries against `shipments` | Epic 2 |

**DO NOT** modify the `Shipment` ORM model — columns already match the CSV mapping.
**DO NOT** load any data into `extracted_documents` — it starts empty.

### Files Changed by This Story

New:
- `backend/app/core/csv_loader.py`
- `backend/data/SCMS_Delivery_History_Dataset.csv`
- `backend/tests/test_story_1_3.py`

Modified:
- `backend/app/main.py` (lifespan: add CSV load + error handling)

### References

- [Source: DATASET_SCHEMA.md] — authoritative column mapping, sentinel values, date formats
- [Source: architecture.md#Data Architecture] — `pd.read_csv()` → bulk insert pattern
- [Source: architecture.md#Startup Idempotency Pattern] — `session.query(Shipment).count() == 0` guard
- [Source: epics.md#Story 1.3] — user story, acceptance criteria
- [Source: deferred-work.md] — lifespan error handling (addressed here)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Three bugs found and fixed during implementation:

1. **Stale pycache `NameError: name 'func' is not defined`** — Old `.pyc` bytecode referenced `func.now()` from a prior iteration of `extracted_document.py`. Fixed by deleting all `__pycache__` directories before re-running tests.

2. **`df.where(pd.notna(df), None)` leaving float NaN in pandas 3.0.1** — The standard pandas NaN→None pattern is insufficient in pandas 3.x with mixed ArrowDtype/StringDtype columns. SQLite `bulk insert` would then receive Python `float('nan')` instead of `None`, causing type errors. Fixed by adding an explicit `_none_if_nan()` per-value cleanup pass after `df.to_dict()`.

3. **`NOT NULL constraint failed: shipments.shipment_mode`** — `DATASET_SCHEMA.md` marked this column NOT NULL, but the real SCMS CSV has 360 rows (3.5%) with NULL Shipment Mode. Discovered via `df['Shipment Mode'].isna().sum()`. Fixed by changing `shipment_mode = Column(Text, nullable=False)` → `Column(Text)` in `shipment.py`.

Additional notes:
- `format="mixed"` required for `pd.to_datetime()` — SCMS CSV contains multiple date formats: `"3/14/13"`, `"2-Jun-06"`, `"2013-06-02"`.
- `select_dtypes(include=["object", "str"])` used instead of `include="object"` alone to avoid `Pandas4Warning` in pandas 3.x.
- The CSV's first column header is `"ID"` (uppercase), not `"id"` — `COLUMN_MAP` must use `"ID"` as the key.
- Architecture docs and epics reference `scms_shipments.csv`; actual Kaggle filename is `SCMS_Delivery_History_Dataset.csv`. Used the real filename; documented the discrepancy in Dev Notes.

### Completion Notes List

- All 10 tests in `test_story_1_3.py` pass.
- Full test suite (36 tests across test_story_1_1.py, test_story_1_2.py, test_story_1_3.py) green.
- ruff lint clean — zero warnings or errors.
- Manual verification: 10,324 rows loaded in ~0.5s; NULL counts: weight_kg=3952, freight_cost_usd=4126, shipment_mode=360. All correct per DATASET_SCHEMA.md.
- CSV committed to repo at `backend/data/SCMS_Delivery_History_Dataset.csv` (UTF-8-sig encoding, BOM prefix).
- `shipment_mode` column made nullable — a deviation from DATASET_SCHEMA.md but required by real data. Documented inline in `shipment.py`.

### File List

New files:
- `backend/app/core/csv_loader.py`
- `backend/data/SCMS_Delivery_History_Dataset.csv`
- `backend/tests/test_story_1_3.py`

Modified files:
- `backend/app/main.py` — lifespan: added CSV load call + structured error handling
- `backend/app/models/shipment.py` — `shipment_mode` changed to nullable

### Review Findings

- [x] [Review][Patch] Bulk insert does not explicitly roll back session on exception — if `session.execute(insert(Shipment), records)` raises (e.g. duplicate PK, constraint violation), the session is left dirty; no `session.rollback()` is called before the `finally: db.close()` in main.py [app/core/csv_loader.py:117]
- [x] [Review][Patch] `"Invoiced Separately"` freight sentinel not covered in test fixture — AC1 lists it as a sentinel for `freight_cost_usd` but no test row exercises it; a regression that stopped nulling it would pass the suite [tests/test_story_1_3.py]
- [x] [Review][Patch] Test CSV fixture missing production D-Mon-YY date format — all 10,324 real CSV rows use `"2-Jun-06"` format; fixture only uses `M/D/YY` and ISO; `format="mixed"` handles both, but a future hardcode to `%m/%d/%y` would silently null every production date and pass tests [tests/test_story_1_3.py]
- [x] [Review][Patch] `pq_first_sent_to_client_date` never asserted + misleading test comment — test comment says `"3/14/13" should be parsed as ISO "2013-03-14"` but that field is never asserted in any test; the comment incorrectly references a different column [tests/test_story_1_3.py:212]
- [x] [Review][Defer] CORS `allow_origins=["*"]` with no credential restriction [app/main.py] — deferred, pre-existing from Story 1.1
- [x] [Review][Defer] Multi-worker race: idempotency check is TOCTOU; concurrent workers both see count=0 and attempt insert, producing duplicate-PK errors [app/core/csv_loader.py:68] — deferred, architectural; current deploy is single-worker uvicorn
- [x] [Review][Defer] `CSV_PATH` resolved at module import time with no env-var override — wrong path in non-standard CWD or packaged deploy [app/core/csv_loader.py:10] — deferred, low risk in Docker; addressed with Dockerfile COPY layout
- [x] [Review][Defer] `pydantic-settings` not declared in `pyproject.toml` — `ModuleNotFoundError` on clean install if not pulled transitively [pyproject.toml] — deferred, pre-existing from Story 1.1
- [x] [Review][Defer] `test_story_1_1.py` uses `TestClient(app)` which hits live `freightmind.db` — test isolation concern [tests/test_story_1_1.py] — deferred, pre-existing from Story 1.1
- [x] [Review][Defer] `autoincrement=False` not set on primary key `id` — safe in SQLite; on Postgres would create SERIAL conflicting with CSV IDs [app/models/shipment.py] — deferred, SQLite-only project at this stage

## Change Log

- 2026-03-30: Story 1.3 created by create-story workflow
- 2026-03-30: Code review completed; 4 patches, 6 deferred, 10 dismissed
