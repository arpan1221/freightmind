"""
Tests for Story 4.2 — Cross-table query execution and combined response (FR26/FR27).

Verifies:
- Mocked UNION ALL spanning shipments + extracted_documents executes on shared route path.
- Answer layer receives linkage context; prompts include cross-table linkage guidance.
- Executed SQL does not embed the user question string (NFR7).
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.prompts import load_prompt
from app.models.extracted_document import ExtractedDocument  # noqa: F401
from app.models.extracted_line_item import ExtractedLineItem  # noqa: F401
from app.models.shipment import Shipment


def _make_db_shipments_and_confirmed_extraction():
    """In-memory DB with one SCMS row and one confirmed extracted invoice (Air mode)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        db.add(
            Shipment(
                id=42,
                project_code="P1",
                country="Nigeria",
                managed_by="PMO - US",
                fulfill_via="Direct Drop",
                product_group="ARV",
                vendor="VendorCo",
                line_item_quantity=10,
                line_item_value=500.0,
                shipment_mode="Air",
                freight_cost_usd=600.0,
            )
        )
        db.add(
            ExtractedDocument(
                source_filename="inv.pdf",
                invoice_number="INV-X",
                shipment_mode="Air",
                total_freight_cost_usd=300.0,
                confirmed_by_user=1,
            )
        )
        db.commit()
    finally:
        db.close()
    return engine, factory


def _get_test_client_with_db(session_factory):
    from app.main import app

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def clear_overrides():
    from app.main import app

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestCrossTableSqlExecution:
    """AC1/4: same route path; UNION ALL spanning both tables executes."""

    def test_union_all_both_tables_returns_rows_and_combined_answer(
        self, clear_overrides
    ):
        _, factory = _make_db_shipments_and_confirmed_extraction()
        client = _get_test_client_with_db(factory)

        safe_sql = (
            "SELECT 'dataset' AS src, AVG(freight_cost_usd) AS avg_f "
            "FROM shipments WHERE shipment_mode = 'Air' AND freight_cost_usd IS NOT NULL "
            "UNION ALL "
            "SELECT 'extracted' AS src, AVG(total_freight_cost_usd) "
            "FROM extracted_documents WHERE shipment_mode = 'Air' AND confirmed_by_user = 1"
        )
        user_question = (
            "Compare average Air freight: my confirmed invoices vs the SCMS dataset"
        )
        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                "refined comparison",
                safe_sql,
                "Dataset average freight for Air is 600 USD; your confirmed uploads average 300 USD.",
                "null",
                '["What about Ocean mode?"]',
            ]
        )

        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": user_question})

        assert response.status_code == 200
        body = response.json()
        assert body.get("error") is None
        sql_out = body["sql"]
        assert "shipments" in sql_out.lower()
        assert "extracted_documents" in sql_out.lower()
        assert "union" in sql_out.lower()
        assert user_question not in sql_out
        assert body["row_count"] == 2
        assert len(body["rows"]) == 2
        assert "600" in body["answer"] or "300" in body["answer"]
        assert mock_client.call.await_count == 6


class TestPromptLinkageGuidance:
    """Prompts encourage cross-table SQL and combined narrative."""

    def test_sql_gen_mentions_union_and_linkage(self):
        body = load_prompt("analytics_sql_gen").lower()
        assert "union all" in body or "union" in body
        assert "cross-table" in body or "linkage" in body or "fr27" in body

    def test_answer_prompt_mentions_both_tables(self):
        body = load_prompt("analytics_answer").lower()
        assert "extracted_documents" in body
        assert "shipments" in body


class TestSqlLinkageHelper:
    """Route helper detects cross-table SQL for answer context."""

    def test_cross_table_detection(self):
        from app.api.routes.analytics import _sql_crosses_shipments_and_extracted

        assert _sql_crosses_shipments_and_extracted(
            "SELECT * FROM shipments JOIN extracted_documents ON 1=1"
        )
        assert not _sql_crosses_shipments_and_extracted(
            "SELECT COUNT(*) FROM shipments"
        )
        # Table name only in SQL comment must not count as cross-table linkage
        assert not _sql_crosses_shipments_and_extracted(
            "SELECT COUNT(*) FROM extracted_documents WHERE confirmed_by_user = 1 -- shipments join"
        )
