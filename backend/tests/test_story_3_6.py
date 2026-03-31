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

    def test_results_ordered_newest_first(self):
        factory = _make_db()
        first_id = _seed_doc(factory, confirmed=1, source_filename="oldest.pdf")
        second_id = _seed_doc(factory, confirmed=1, source_filename="newest.pdf")
        client = self._get_client(factory)
        items = client.get("/api/documents/extractions").json()["extractions"]
        assert len(items) == 2
        assert items[0]["extraction_id"] == second_id
        assert items[1]["extraction_id"] == first_id

    def test_limit_offset_pagination(self):
        factory = _make_db()
        _seed_doc(factory, confirmed=1, source_filename="a.pdf")
        mid_id = _seed_doc(factory, confirmed=1, source_filename="b.pdf")
        _seed_doc(factory, confirmed=1, source_filename="c.pdf")
        client = self._get_client(factory)
        page = client.get(
            "/api/documents/extractions",
            params={"limit": 1, "offset": 1},
        ).json()["extractions"]
        assert len(page) == 1
        assert page[0]["extraction_id"] == mid_id
        assert page[0]["filename"] == "b.pdf"

    def test_endpoint_in_openapi_spec(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        assert "/api/documents/extractions" in spec["paths"]
        assert "get" in spec["paths"]["/api/documents/extractions"]
