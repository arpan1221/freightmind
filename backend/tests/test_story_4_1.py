"""
Tests for Story 4.1 — Schema-aware planner: both tables in analytics prompt context.

Covers:
- AC1: Prompts reference shipments + extracted_documents (and line items where relevant).
- AC2: No confirmed extractions + document-themed question → honest answer, no SQL error.
- AC3: With confirmed row + mocked LLM SQL → route executes SELECT on extracted_documents.
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.prompts import load_prompt
from app.models.extracted_document import ExtractedDocument  # noqa: F401 — register model
from app.models.extracted_line_item import ExtractedLineItem  # noqa: F401
from app.models.shipment import Shipment  # noqa: F401

from app.api.routes.analytics import (
    _count_confirmed_extractions,
    _question_targets_extracted_documents,
)


def _make_in_memory_db_minimal_shipments_only():
    """Same pattern as test_story_2_1 — no extracted_documents table."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE shipments (
                id INTEGER PRIMARY KEY,
                shipment_mode TEXT,
                freight_cost_usd REAL,
                country TEXT,
                product_group TEXT
            )
        """)
        )
        conn.execute(
            text("""
            INSERT INTO shipments VALUES
                (1, 'Air', 1000.0, 'Nigeria', 'ARV')
        """)
        )
    factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, factory


def _make_in_memory_db_full_with_confirmed_extraction():
    """ORM-created schema including extracted_documents."""
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
            ExtractedDocument(
                source_filename="demo.pdf",
                invoice_number="INV-1",
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
    client = TestClient(app)
    return client


class TestPromptsIncludeBothTables:
    """AC1: planner, system, and SQL gen prompts describe both data sources."""

    def test_analytics_sql_gen_mentions_extracted_documents_and_shipments(self):
        body = load_prompt("analytics_sql_gen")
        assert "shipments" in body.lower()
        assert "extracted_documents" in body.lower()
        assert "confirmed_by_user" in body.lower()

    def test_analytics_planner_mentions_extracted_documents(self):
        body = load_prompt("analytics_planner")
        assert "extracted_documents" in body.lower()
        assert "confirmed_by_user" in body.lower() or "confirmed" in body.lower()

    def test_analytics_system_mentions_both_tables(self):
        body = load_prompt("analytics_system")
        assert "shipments" in body.lower()
        assert "extracted_documents" in body.lower()


class TestHeuristics:
    def test_question_targets_extracted_documents_examples(self):
        assert _question_targets_extracted_documents(
            "How many invoices have I uploaded?"
        )
        assert _question_targets_extracted_documents("Count my uploaded documents")
        assert _question_targets_extracted_documents("List my extractions")
        assert _question_targets_extracted_documents("What did I upload?")
        assert _question_targets_extracted_documents("Show my uploads")
        assert not _question_targets_extracted_documents(
            "What is the average freight cost by shipment mode?"
        )
        assert not _question_targets_extracted_documents(
            "How many shipments are there to Nigeria?"
        )

    def test_count_confirmed_extractions_minimal_db_returns_zero(self):
        _, factory = _make_in_memory_db_minimal_shipments_only()
        db = factory()
        try:
            assert _count_confirmed_extractions(db) == 0
        finally:
            db.close()

    def test_count_confirmed_extractions_with_confirmed_row(self):
        _, factory = _make_in_memory_db_full_with_confirmed_extraction()
        db = factory()
        try:
            assert _count_confirmed_extractions(db) == 1
        finally:
            db.close()


class TestNoConfirmedExtractionsHonestAnswer:
    """AC2: empty / no confirmed path."""

    def setup_method(self):
        from app.main import app

        app.dependency_overrides.clear()

    def test_document_question_no_table_returns_honest_answer_without_extra_llm_calls(
        self,
    ):
        _, factory = _make_in_memory_db_minimal_shipments_only()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=AssertionError(
                "classify_intent should not run when zero confirmed + document question"
            )
        )

        with patch("app.api.routes.analytics.ModelClient.for_analytics", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "How many invoices have I uploaded?"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert body["sql"] == ""
        assert body["row_count"] == 0
        assert (
            "no confirmed" in body["answer"].lower()
            or "no confirmed uploaded" in body["answer"].lower()
        )
        assert "documents" in body["answer"].lower()
        assert mock_client.call.await_count == 0

    def test_shipment_only_question_still_runs_pipeline(self):
        _, factory = _make_in_memory_db_minimal_shipments_only()
        client = _get_test_client_with_db(factory)

        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                "refined",
                "SELECT COUNT(*) AS cnt FROM shipments",
                "There are 1 shipments.",
                "null",
                '["Q1?"]',
            ]
        )

        with patch("app.api.routes.analytics.ModelClient.for_analytics", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "How many shipments are in the dataset?"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert "shipments" in body["sql"].lower()
        assert body["row_count"] >= 1


class TestConfirmedExtractionSqlPath:
    """With confirmed data, document-style question executes mocked SQL on extracted_documents."""

    def setup_method(self):
        from app.main import app

        app.dependency_overrides.clear()

    def test_extracted_documents_select_executes(self):
        _, factory = _make_in_memory_db_full_with_confirmed_extraction()
        client = _get_test_client_with_db(factory)

        safe_sql = (
            "SELECT COUNT(*) AS n FROM extracted_documents WHERE confirmed_by_user = 1"
        )
        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                "How many confirmed invoices?",
                safe_sql,
                "You have 1 confirmed invoice.",
                "null",
                '["Q1?"]',
            ]
        )

        with patch("app.api.routes.analytics.ModelClient.for_analytics", return_value=mock_client):
            response = client.post(
                "/api/query",
                json={"question": "How many invoices have I uploaded?"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert "extracted_documents" in body["sql"].lower()
        assert body["row_count"] == 1
        assert body["rows"][0][0] == 1
