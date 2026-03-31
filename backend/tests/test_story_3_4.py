import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

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
    """Insert one ExtractedDocument row and return its id."""
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
        resp = client.post(
            "/api/documents/confirm",
            json={
                "extraction_id": doc_id,
                "corrections": {"invoice_number": "INV-999"},
            },
        )
        assert resp.status_code == 200
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
            json={
                "extraction_id": doc_id,
                "corrections": {"nonexistent_field": "value"},
            },
        )
        assert resp.status_code == 422

    def test_invalid_shipment_mode_returns_422(self):
        engine, factory = _make_db()
        doc_id = _seed_doc(factory)
        client = self._get_client(factory)
        resp = client.post(
            "/api/documents/confirm",
            json={
                "extraction_id": doc_id,
                "corrections": {"shipment_mode": "InvalidMode"},
            },
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
        assert msg is None

    def test_invalid_key_returns_false(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({"bad_field": "x"}, object())
        assert valid is False
        assert msg is not None
        assert "bad_field" in msg

    def test_valid_shipment_modes_accepted(self):
        verifier = ExtractionVerifier()
        for mode in ("Air", "Ocean", "Truck", "Air Charter"):
            valid, _ = verifier.validate_corrections({"shipment_mode": mode}, object())
            assert valid is True

    def test_invalid_shipment_mode_rejected(self):
        verifier = ExtractionVerifier()
        valid, msg = verifier.validate_corrections({"shipment_mode": "Rail"}, object())
        assert valid is False
        assert msg is not None
        assert "Rail" in msg
