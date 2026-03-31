"""
Tests for Story 3.5 — Cancel endpoint DELETE /extract/{extraction_id}

Verifies:
- AC1: Valid unconfirmed extraction_id → row deleted from DB, HTTP 200 returned
- AC2: Unknown extraction_id → HTTP 404 with error="not_found"
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db, Base
from app.models.extracted_document import ExtractedDocument
from app.models.extracted_line_item import ExtractedLineItem


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, Factory


def _seed_doc(factory, with_line_item: bool = False) -> int:
    """Insert an ExtractedDocument (and optionally a line item). Returns extraction_id."""
    db = factory()
    try:
        doc = ExtractedDocument(source_filename="invoice.pdf", confirmed_by_user=0)
        db.add(doc)
        db.flush()
        if with_line_item:
            db.add(ExtractedLineItem(document_id=doc.id, description="Widget", quantity=1))
        db.commit()
        return doc.id
    finally:
        db.close()


def _get_client(factory):
    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCancelExtraction:
    def setup_method(self):
        app.dependency_overrides.clear()

    def test_valid_extraction_id_returns_200(self):
        _, factory = _make_db()
        extraction_id = _seed_doc(factory)
        client = _get_client(factory)

        resp = client.delete(f"/api/extract/{extraction_id}")

        assert resp.status_code == 200

    def test_success_response_body(self):
        _, factory = _make_db()
        extraction_id = _seed_doc(factory)
        client = _get_client(factory)

        resp = client.delete(f"/api/extract/{extraction_id}")
        body = resp.json()

        assert body["extraction_id"] == extraction_id
        assert body["deleted"] is True
        assert isinstance(body["message"], str)
        assert len(body["message"]) > 0

    def test_document_deleted_from_db(self):
        _, factory = _make_db()
        extraction_id = _seed_doc(factory)
        client = _get_client(factory)

        client.delete(f"/api/extract/{extraction_id}")

        db = factory()
        try:
            doc = db.get(ExtractedDocument, extraction_id)
            assert doc is None
        finally:
            db.close()

    def test_associated_line_items_deleted_via_cascade(self):
        _, factory = _make_db()
        extraction_id = _seed_doc(factory, with_line_item=True)
        client = _get_client(factory)

        # Verify line item exists before delete
        db = factory()
        try:
            items_before = db.query(ExtractedLineItem).filter_by(document_id=extraction_id).all()
            assert len(items_before) == 1
        finally:
            db.close()

        client.delete(f"/api/extract/{extraction_id}")

        db = factory()
        try:
            items_after = db.query(ExtractedLineItem).filter_by(document_id=extraction_id).all()
            assert items_after == []
        finally:
            db.close()

    def test_unknown_extraction_id_returns_404(self):
        _, factory = _make_db()
        client = _get_client(factory)

        resp = client.delete("/api/extract/99999")

        assert resp.status_code == 404

    def test_unknown_extraction_id_error_body(self):
        _, factory = _make_db()
        client = _get_client(factory)

        resp = client.delete("/api/extract/99999")
        body = resp.json()

        assert body["error"] is True
        assert body["error_type"] == "not_found"
        assert "99999" in body["message"]

    def test_endpoint_in_openapi_spec(self):
        client = TestClient(app)
        spec = client.get("/openapi.json").json()
        assert "/api/extract/{extraction_id}" in spec["paths"]
        assert "delete" in spec["paths"]["/api/extract/{extraction_id}"]
