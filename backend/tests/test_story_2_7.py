"""
Tests for Story 2.7 — Analytics agent standalone invocability (FR41)

Verifies:
- AC1: POST /api/query works on a minimal app that imports NO extraction modules
- AC2: All analytics module source files contain zero extraction-related imports
         (static AST analysis — guards against future contamination)
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import ast
import pathlib
import sys
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routes import analytics
from app.core.database import get_db


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = pathlib.Path(__file__).parent.parent

_ANALYTICS_MODULE_PATHS = [
    _BACKEND_ROOT / "app/agents/analytics/__init__.py",
    _BACKEND_ROOT / "app/agents/analytics/planner.py",
    _BACKEND_ROOT / "app/agents/analytics/executor.py",
    _BACKEND_ROOT / "app/agents/analytics/verifier.py",
    _BACKEND_ROOT / "app/api/routes/analytics.py",
    _BACKEND_ROOT / "app/schemas/analytics.py",
]

_EXTRACTION_MARKERS = ("extraction", "extracted", "extract")


def _make_minimal_analytics_app():
    """Build a FastAPI app with ONLY the analytics router.

    Does NOT use app.main — main.py imports extraction models for DB setup,
    which would pollute sys.modules and invalidate the isolation assertions.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE shipments (
                id INTEGER PRIMARY KEY,
                shipment_mode TEXT,
                freight_cost_usd REAL,
                country TEXT,
                product_group TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO shipments VALUES
                (1, 'Air', 1000.0, 'Nigeria', 'ARV'),
                (2, 'Ocean', 500.0, 'Uganda', 'HRDT')
        """))
    Factory = sessionmaker(engine, autocommit=False, autoflush=False)

    app = FastAPI()
    app.include_router(analytics.router, prefix="/api")

    def override_get_db():
        db = Factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


def _make_mock_client():
    """Return a ModelClient mock wired for the full 2.2+ pipeline (6 calls)."""
    mock = MagicMock()
    mock.call = AsyncMock(side_effect=[
        '{"intent": "answerable"}',              # classify_intent
        "How many shipments are there?",          # plan
        "SELECT COUNT(*) AS cnt FROM shipments",  # generate_sql
        "There are 2 shipments.",                 # _generate_answer
        "null",                                   # _generate_chart_config
        '["Q1?", "Q2?"]',                         # _generate_follow_ups
    ])
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# AC1: Minimal analytics-only app — POST /api/query works without extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsStandaloneApp:
    """POST /api/query works on a minimal app that has never loaded extraction modules."""

    def test_post_query_on_minimal_app_returns_200(self):
        """AC1: Analytics route works on a minimal app with no extraction imports."""
        app = _make_minimal_analytics_app()
        client = TestClient(app)

        mock_client = _make_mock_client()
        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "how many?"})

        assert response.status_code == 200

    def test_post_query_minimal_app_correct_shape(self):
        """AC1: Response has correct shape on standalone app."""
        app = _make_minimal_analytics_app()
        client = TestClient(app)

        mock_client = _make_mock_client()
        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "how many?"})

        body = response.json()
        assert "answer" in body
        assert "sql" in body
        assert "columns" in body
        assert "rows" in body
        assert "row_count" in body
        assert body["error"] is None

    def test_post_query_minimal_app_executes_sql(self):
        """AC1: Analytics executes SQL against the in-memory DB — returns real row count."""
        app = _make_minimal_analytics_app()
        client = TestClient(app)

        mock_client = _make_mock_client()
        with patch("app.api.routes.analytics.ModelClient", return_value=mock_client):
            response = client.post("/api/query", json={"question": "how many?"})

        body = response.json()
        assert body["row_count"] == 1  # COUNT(*) returns 1 row
        assert body["columns"] == ["cnt"]
        assert body["rows"] == [[2]]   # 2 shipments in the test DB


# ─────────────────────────────────────────────────────────────────────────────
# AC2: Static AST analysis — no extraction imports in analytics modules
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyticsModuleIsolation:
    """All analytics module files must have zero extraction-related imports (AC2).

    Static AST analysis is the most reliable isolation test — it cannot produce
    false positives from sys.modules contamination by other tests.
    """

    @pytest.mark.parametrize("filepath", _ANALYTICS_MODULE_PATHS)
    def test_no_extraction_imports(self, filepath):
        """AC2: Each analytics module file must not import any extraction module."""
        assert filepath.exists(), f"Expected file not found: {filepath}"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(marker in module for marker in _EXTRACTION_MARKERS):
                    violations.append(
                        f"line {node.lineno}: from {module} import ..."
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(marker in alias.name for marker in _EXTRACTION_MARKERS):
                        violations.append(
                            f"line {node.lineno}: import {alias.name}"
                        )

        assert not violations, (
            f"{filepath} contains extraction import(s):\n"
            + "\n".join(violations)
        )
