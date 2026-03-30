"""
Tests for Story 1.3 — Auto-load SCMS CSV into shipments table on cold start

Verifies:
- AC1: empty table + valid CSV → ~10,324 rows loaded, NULLs for sentinel values, ISO dates
- AC2: populated table → load is skipped (idempotent)
- AC3: missing CSV → FileNotFoundError with path in message
- String whitespace → stripped
"""
import os
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_csv(tmp_path) -> Path:
    """3-row synthetic CSV covering all edge cases."""
    rows = [
        {
            "ID": 1,
            "Project Code": "SC-003",
            "PQ #": None,
            "PO / SO #": None,
            "ASN/DN #": None,
            "Country": " Nigeria ",          # leading/trailing whitespace → stripped
            "Managed By": "PMO - US",
            "Fulfill Via": "Direct Drop",
            "Vendor INCO Term": "EXW",
            "Shipment Mode": "Air",
            "PQ First Sent to Client Date": "3/14/13",   # non-ISO date → parsed to ISO
            "PO Sent to Vendor Date": "4/3/13",
            "Scheduled Delivery Date": "6/11/13",
            "Delivered to Client Date": "6/19/13",
            "Delivery Recorded Date": "6/19/13",
            "Product Group": "ARV",
            "Sub Classification": "Adult",
            "Vendor": "ABBVIE",
            "Item Description": "Lopinavir 200mg",
            "Molecule/Test Type": "Lopinavir",
            "Brand": None,
            "Dosage": "200mg",
            "Dosage Form": "Tablet",
            "Unit of Measure (Per Pack)": 120,
            "Line Item Quantity": 1200,
            "Line Item Value": 18000.0,
            "Pack Price": 15.0,
            "Unit Price": 0.125,
            "Manufacturing Site": "Abbvie Inc.",
            "First Line Designation": "Yes",
            "Weight (Kilograms)": 1500.0,
            "Freight Cost (USD)": 5765.40,
            "Line Item Insurance (USD)": 120.0,
        },
        {
            "ID": 2,
            "Project Code": "SC-003",
            "PQ #": None,
            "PO / SO #": None,
            "ASN/DN #": None,
            "Country": "Zambia",
            "Managed By": "SCMS",
            "Fulfill Via": "Direct Drop",
            "Vendor INCO Term": "FCA",
            "Shipment Mode": "Ocean",
            "PQ First Sent to Client Date": None,
            "PO Sent to Vendor Date": "6/1/13",
            "Scheduled Delivery Date": "9/1/13",
            "Delivered to Client Date": None,
            "Delivery Recorded Date": None,
            "Product Group": "HRDT",
            "Sub Classification": "HIV test",
            "Vendor": "CHEMBIO",
            "Item Description": "HIV test kit",
            "Molecule/Test Type": "HIV test",
            "Brand": "Sure Check",
            "Dosage": None,
            "Dosage Form": "Test Kit",
            "Unit of Measure (Per Pack)": 20,
            "Line Item Quantity": 5000,
            "Line Item Value": 22500.0,
            "Pack Price": 4.5,
            "Unit Price": 0.225,
            "Manufacturing Site": "Chembio",
            "First Line Designation": "No",
            "Weight (Kilograms)": "Weight Captured Separately",    # sentinel → NULL
            "Freight Cost (USD)": "Freight Included in Commodity Cost",  # sentinel → NULL
            "Line Item Insurance (USD)": None,
        },
        {
            "ID": 3,
            "Project Code": "SC-004",
            "PQ #": None,
            "PO / SO #": None,
            "ASN/DN #": None,
            "Country": "Kenya",
            "Managed By": "PMO - US",
            "Fulfill Via": "From RDC",
            "Vendor INCO Term": None,
            "Shipment Mode": "Truck",
            "PQ First Sent to Client Date": None,
            "PO Sent to Vendor Date": "2014-01-01",
            "Scheduled Delivery Date": "2014-03-01",
            "Delivered to Client Date": None,
            "Delivery Recorded Date": None,
            "Product Group": "ANTM",
            "Sub Classification": None,
            "Vendor": "CIPLA",
            "Item Description": None,
            "Molecule/Test Type": None,
            "Brand": None,
            "Dosage": None,
            "Dosage Form": None,
            "Unit of Measure (Per Pack)": None,
            "Line Item Quantity": 200,
            "Line Item Value": 800.0,
            "Pack Price": None,
            "Unit Price": None,
            "Manufacturing Site": None,
            "First Line Designation": None,
            "Weight (Kilograms)": 45.0,
            "Freight Cost (USD)": 320.0,
            "Line Item Insurance (USD)": 8.0,
        },
    ]
    csv_path = tmp_path / "SCMS_Delivery_History_Dataset.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def test_session(tmp_path):
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    # Import models to register them on Base.metadata
    import app.models.extracted_document  # noqa: F401
    import app.models.extracted_line_item  # noqa: F401
    import app.models.shipment  # noqa: F401
    from app.core.database import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# AC1: CSV loaded correctly into empty table
# ---------------------------------------------------------------------------

class TestLoadFromCsv:
    def test_loads_all_rows(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        count = load_shipments_from_csv(test_session, test_csv)

        assert count == 3
        assert test_session.query(Shipment).count() == 3

    def test_sentinel_weight_becomes_null(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=2).one()
        assert row.weight_kg is None, "sentinel 'Weight Captured Separately' must be NULL"

    def test_sentinel_freight_becomes_null(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=2).one()
        assert row.freight_cost_usd is None, (
            "sentinel 'Freight Included in Commodity Cost' must be NULL"
        )

    def test_numeric_weight_preserved(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=1).one()
        assert row.weight_kg == pytest.approx(1500.0)
        assert row.freight_cost_usd == pytest.approx(5765.40)

    def test_date_stored_as_iso_string(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=1).one()
        # Row 1 uses M/D/YY format — all five dates should be stored as ISO YYYY-MM-DD
        assert row.pq_first_sent_to_client_date == "2013-03-14"  # "3/14/13"
        assert row.scheduled_delivery_date == "2013-06-11"
        assert row.delivered_to_client_date == "2013-06-19"

    def test_null_date_stored_as_none(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=2).one()
        assert row.delivered_to_client_date is None
        assert row.pq_first_sent_to_client_date is None

    def test_whitespace_stripped_from_string_column(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)

        row = test_session.query(Shipment).filter_by(id=1).one()
        # CSV has " Nigeria " with spaces — should be stored as "Nigeria"
        assert row.country == "Nigeria"


# ---------------------------------------------------------------------------
# AC2: Idempotency — second load skipped
# ---------------------------------------------------------------------------

    def test_sentinel_invoiced_separately_becomes_null(self, test_session, tmp_path):
        """'Invoiced Separately' is a second real sentinel for freight_cost_usd → must be NULL."""
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        rows = [
            {
                "ID": 10, "Project Code": "SC-001", "PQ #": None, "PO / SO #": None,
                "ASN/DN #": None, "Country": "Uganda", "Managed By": "SCMS",
                "Fulfill Via": "Direct Drop", "Vendor INCO Term": "EXW",
                "Shipment Mode": "Air",
                "PQ First Sent to Client Date": None, "PO Sent to Vendor Date": None,
                "Scheduled Delivery Date": None, "Delivered to Client Date": None,
                "Delivery Recorded Date": None,
                "Product Group": "ARV", "Sub Classification": None,
                "Vendor": "CIPLA", "Item Description": None, "Molecule/Test Type": None,
                "Brand": None, "Dosage": None, "Dosage Form": None,
                "Unit of Measure (Per Pack)": 60, "Line Item Quantity": 500,
                "Line Item Value": 1000.0, "Pack Price": 2.0, "Unit Price": 0.033,
                "Manufacturing Site": None, "First Line Designation": None,
                "Weight (Kilograms)": 30.0,
                "Freight Cost (USD)": "Invoiced Separately",   # second real sentinel → NULL
                "Line Item Insurance (USD)": None,
            }
        ]
        csv_path = tmp_path / "sentinel_test.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        load_shipments_from_csv(test_session, csv_path)

        row = test_session.query(Shipment).filter_by(id=10).one()
        assert row.freight_cost_usd is None, (
            "sentinel 'Invoiced Separately' must be NULL"
        )

    def test_d_mon_yy_date_format_parsed(self, test_session, tmp_path):
        """D-Mon-YY format (e.g. '2-Jun-06') is the dominant format in the real CSV."""
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        rows = [
            {
                "ID": 20, "Project Code": "SC-002", "PQ #": None, "PO / SO #": None,
                "ASN/DN #": None, "Country": "Mozambique", "Managed By": "SCMS",
                "Fulfill Via": "Direct Drop", "Vendor INCO Term": "EXW",
                "Shipment Mode": "Ocean",
                "PQ First Sent to Client Date": "2-Jun-06",    # D-Mon-YY → 2006-06-02
                "PO Sent to Vendor Date": "15-Mar-07",          # D-Mon-YY → 2007-03-15
                "Scheduled Delivery Date": None,
                "Delivered to Client Date": "1-Aug-07",         # D-Mon-YY → 2007-08-01
                "Delivery Recorded Date": None,
                "Product Group": "ARV", "Sub Classification": None,
                "Vendor": "ABBVIE", "Item Description": None, "Molecule/Test Type": None,
                "Brand": None, "Dosage": None, "Dosage Form": None,
                "Unit of Measure (Per Pack)": 60, "Line Item Quantity": 1000,
                "Line Item Value": 5000.0, "Pack Price": 5.0, "Unit Price": 0.083,
                "Manufacturing Site": None, "First Line Designation": None,
                "Weight (Kilograms)": 50.0, "Freight Cost (USD)": 200.0,
                "Line Item Insurance (USD)": 10.0,
            }
        ]
        csv_path = tmp_path / "dmon_test.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        load_shipments_from_csv(test_session, csv_path)

        row = test_session.query(Shipment).filter_by(id=20).one()
        assert row.pq_first_sent_to_client_date == "2006-06-02", "D-Mon-YY must parse to ISO"
        assert row.po_sent_to_vendor_date == "2007-03-15"
        assert row.delivered_to_client_date == "2007-08-01"


class TestIdempotency:
    def test_second_load_returns_zero(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv

        load_shipments_from_csv(test_session, test_csv)
        result = load_shipments_from_csv(test_session, test_csv)

        assert result == 0

    def test_second_load_does_not_duplicate_rows(self, test_session, test_csv):
        from app.core.csv_loader import load_shipments_from_csv
        from app.models.shipment import Shipment

        load_shipments_from_csv(test_session, test_csv)
        load_shipments_from_csv(test_session, test_csv)

        assert test_session.query(Shipment).count() == 3


# ---------------------------------------------------------------------------
# AC3: Missing CSV → FileNotFoundError
# ---------------------------------------------------------------------------

class TestMissingCsv:
    def test_raises_file_not_found_for_missing_csv(self, test_session, tmp_path):
        from app.core.csv_loader import load_shipments_from_csv

        missing = tmp_path / "does_not_exist.csv"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_shipments_from_csv(test_session, missing)

        assert str(missing.resolve()) in str(exc_info.value)
