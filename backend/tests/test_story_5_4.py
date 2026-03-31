"""
Tests for Story 5.4 — Unsafe SQL and failed execution as ErrorResponse with detail.sql (FR32).
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _make_in_memory_db():
    """In-memory SQLite with ``shipments`` — mirrors test_story_2_1 helper."""
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
                (1, 'Air', 1000.0, 'Nigeria', 'ARV'),
                (2, 'Ocean', 500.0, 'Uganda', 'HRDT'),
                (3, 'Truck', 200.0, 'Kenya', 'ARV')
        """)
        )
    factory = sessionmaker(engine, autocommit=False, autoflush=False)
    return engine, factory


def _get_test_client_with_db(session_factory):
    from app.core.database import get_db
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
    """Prevent ``dependency_overrides`` leaking to other tests (matches test_story_4_2)."""
    from app.main import app

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestStory54StructuredSqlErrors:
    def test_unsafe_sql_returns_400_error_envelope_with_full_sql(
        self, clear_overrides
    ) -> None:
        """Verifier rejection → 400, error_type unsafe_sql, detail.sql = full rejected query."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)
        rejected_sql = "DROP TABLE shipments"
        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                "refined",
                rejected_sql,
            ]
        )
        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "nuke data"})

        assert response.status_code == 400
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "unsafe_sql"
        assert isinstance(body.get("message"), str)
        assert body["detail"]["sql"] == rejected_sql

    def test_sql_execution_error_returns_422_when_verifier_passes(
        self, clear_overrides
    ) -> None:
        """SQLite/SQLAlchemy execution failure → 422, error_type sql_execution_error, detail.sql."""
        _, factory = _make_in_memory_db()
        client = _get_test_client_with_db(factory)
        bad_sql = "SELECT no_such_column_xyz FROM shipments"
        mock_client = MagicMock()
        mock_client.call = AsyncMock(
            side_effect=[
                '{"intent": "answerable"}',
                "refined",
                bad_sql,
            ]
        )
        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "show mystery column"})

        assert response.status_code == 422
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "sql_execution_error"
        assert isinstance(body.get("message"), str)
        assert body["detail"]["sql"] == bad_sql
