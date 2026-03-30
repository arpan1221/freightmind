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
