"""
Tests for Story 1.2 — Auto-create database schema and indexes on startup

Verifies:
- AC1: Fresh DB gets all 3 tables + required indexes after init_db()
- AC2: init_db() is idempotent — calling twice raises no error
- AC3: get_db() yields a session and closes it on exit
"""
import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Provide required env vars before importing app modules
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from app.core.database import Base, get_db  # noqa: E402
import app.models.shipment  # noqa: F401, E402 — registers Shipment on Base.metadata
import app.models.extracted_document  # noqa: F401, E402
import app.models.extracted_line_item  # noqa: F401, E402
from app.models.shipment import Shipment  # noqa: E402
from app.models.extracted_document import ExtractedDocument  # noqa: E402
from app.models.extracted_line_item import ExtractedLineItem  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_engine():
    """Fresh in-memory SQLite engine per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
    yield engine
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)


@pytest.fixture
def db_session(mem_engine):
    Session = sessionmaker(mem_engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# AC1: All tables and indexes created on fresh DB
# ---------------------------------------------------------------------------

class TestTableCreation:
    def test_all_three_tables_exist(self, mem_engine):
        inspector = inspect(mem_engine)
        tables = inspector.get_table_names()
        assert "shipments" in tables
        assert "extracted_documents" in tables
        assert "extracted_line_items" in tables

    def test_shipments_has_required_columns(self, mem_engine):
        inspector = inspect(mem_engine)
        cols = {c["name"] for c in inspector.get_columns("shipments")}
        required = {
            "id", "project_code", "country", "managed_by", "fulfill_via",
            "shipment_mode", "product_group", "vendor",
            "line_item_quantity", "line_item_value",
            "weight_kg", "freight_cost_usd", "po_sent_to_vendor_date",
            "scheduled_delivery_date",
        }
        assert required.issubset(cols)

    def test_extracted_documents_has_required_columns(self, mem_engine):
        inspector = inspect(mem_engine)
        cols = {c["name"] for c in inspector.get_columns("extracted_documents")}
        required = {
            "id", "source_filename", "destination_country", "shipment_mode",
            "confirmed_by_user", "extracted_at", "extraction_confidence",
        }
        assert required.issubset(cols)

    def test_extracted_line_items_has_required_columns(self, mem_engine):
        inspector = inspect(mem_engine)
        cols = {c["name"] for c in inspector.get_columns("extracted_line_items")}
        required = {"id", "document_id", "description", "quantity", "unit_price", "total_price", "confidence"}
        assert required.issubset(cols)


class TestIndexCreation:
    def test_shipments_indexes_exist(self, mem_engine):
        inspector = inspect(mem_engine)
        index_names = {idx["name"] for idx in inspector.get_indexes("shipments")}
        assert "idx_shipments_country" in index_names
        assert "idx_shipments_shipment_mode" in index_names
        assert "idx_shipments_vendor" in index_names
        assert "idx_shipments_product_group" in index_names
        assert "idx_shipments_scheduled_delivery" in index_names

    def test_extracted_documents_indexes_exist(self, mem_engine):
        inspector = inspect(mem_engine)
        index_names = {idx["name"] for idx in inspector.get_indexes("extracted_documents")}
        assert "idx_extracted_destination" in index_names
        assert "idx_extracted_shipment_mode" in index_names


# ---------------------------------------------------------------------------
# AC2: Idempotency — calling create_all twice raises no error
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_create_all_twice_no_error(self, mem_engine):
        # Should not raise — SQLAlchemy uses checkfirst=True internally
        Base.metadata.create_all(bind=mem_engine)
        Base.metadata.create_all(bind=mem_engine)

    def test_tables_unchanged_after_second_create(self, mem_engine):
        Base.metadata.create_all(bind=mem_engine)
        inspector = inspect(mem_engine)
        tables_after = set(inspector.get_table_names())
        assert {"shipments", "extracted_documents", "extracted_line_items"}.issubset(tables_after)


# ---------------------------------------------------------------------------
# AC3: get_db() yields a session and closes it
# ---------------------------------------------------------------------------

class TestGetDb:
    def test_get_db_yields_session(self, mem_engine, monkeypatch):
        from app.core import database as db_module
        monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=mem_engine))
        gen = get_db()
        session = next(gen)
        assert session is not None
        # Exhaust the generator (triggers finally: db.close())
        with pytest.raises(StopIteration):
            next(gen)

    def test_get_db_session_is_closed_after_use(self, mem_engine, monkeypatch):
        from app.core import database as db_module
        monkeypatch.setattr(db_module, "SessionLocal", sessionmaker(bind=mem_engine))
        closed_calls = []
        gen = get_db()
        session = next(gen)
        # Monkeypatch close on the live session to track the call
        original_close = session.close
        session.close = lambda: (closed_calls.append(True), original_close())[1]
        with pytest.raises(StopIteration):
            next(gen)
        # The finally block in get_db() must have called close()
        assert len(closed_calls) == 1


# ---------------------------------------------------------------------------
# ORM round-trip: insert and query each model
# ---------------------------------------------------------------------------

class TestOrmRoundTrip:
    def test_shipment_insert_and_query(self, db_session):
        shipment = Shipment(
            id=1,
            project_code="PRJ-001",
            country="Nigeria",
            managed_by="PMO - US",
            fulfill_via="Direct Drop",
            shipment_mode="Air",
            product_group="ARV",
            vendor="Acme Pharma",
            line_item_quantity=100,
            line_item_value=5000.0,
        )
        db_session.add(shipment)
        db_session.commit()
        result = db_session.query(Shipment).filter_by(id=1).one()
        assert result.country == "Nigeria"
        assert result.shipment_mode == "Air"
        assert result.weight_kg is None  # nullable by default

    def test_extracted_document_insert_and_query(self, db_session):
        doc = ExtractedDocument(
            source_filename="invoice_001.pdf",
            destination_country="Nigeria",
            shipment_mode="Air",
            confirmed_by_user=0,
        )
        db_session.add(doc)
        db_session.commit()
        result = db_session.query(ExtractedDocument).first()
        assert result.source_filename == "invoice_001.pdf"
        assert result.confirmed_by_user == 0

    def test_extracted_line_item_insert_and_cascade_delete(self, db_session):
        doc = ExtractedDocument(source_filename="invoice_002.pdf")
        db_session.add(doc)
        db_session.flush()

        item = ExtractedLineItem(
            document_id=doc.id,
            description="ARV tablets",
            quantity=50,
            unit_price=10.0,
            total_price=500.0,
            confidence=0.95,
        )
        db_session.add(item)
        db_session.commit()

        # Cascade delete: deleting parent removes line items
        db_session.delete(doc)
        db_session.commit()
        assert db_session.query(ExtractedLineItem).count() == 0

    def test_confirmed_by_user_default_is_zero(self, db_session):
        doc = ExtractedDocument(source_filename="invoice_003.pdf")
        db_session.add(doc)
        db_session.commit()
        result = db_session.query(ExtractedDocument).first()
        assert result.confirmed_by_user == 0

    def test_foreign_key_constraint_enforced(self, mem_engine):
        """document_id must reference a valid extracted_documents.id."""
        with mem_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        "INSERT INTO extracted_line_items (document_id, description) "
                        "VALUES (99999, 'orphan item')"
                    )
                )
