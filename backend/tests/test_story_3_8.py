"""
Tests for Story 3.8 — Vision extraction standalone invocability (FR42)

Verifies:
- AC1: POST /api/documents/extract works on a minimal app that imports NO analytics modules
- AC2: All extraction module source files contain zero analytics-related imports
         (static AST analysis — guards against future contamination)
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import ast
import pathlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routes import documents, extraction
from app.core.database import get_db
from app.schemas.documents import ExtractedField


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = pathlib.Path(__file__).parent.parent

_EXTRACTION_MODULE_PATHS = [
    _BACKEND_ROOT / "app/agents/extraction/__init__.py",
    _BACKEND_ROOT / "app/agents/extraction/planner.py",
    _BACKEND_ROOT / "app/agents/extraction/executor.py",
    _BACKEND_ROOT / "app/agents/extraction/verifier.py",
    _BACKEND_ROOT / "app/agents/extraction/normaliser.py",
    _BACKEND_ROOT / "app/api/routes/documents.py",
    _BACKEND_ROOT / "app/api/routes/extraction.py",
    _BACKEND_ROOT / "app/schemas/documents.py",
    _BACKEND_ROOT / "app/schemas/extraction.py",
]

_ANALYTICS_MARKERS = ("analytics",)

_HEADER_FIELDS = [
    "invoice_number",
    "invoice_date",
    "shipper_name",
    "consignee_name",
    "origin_country",
    "destination_country",
    "shipment_mode",
    "carrier_vendor",
    "total_weight_kg",
    "total_freight_cost_usd",
    "total_insurance_usd",
    "payment_terms",
    "delivery_date",
]

_NUMERIC_FIELDS = frozenset({"total_weight_kg", "total_freight_cost_usd", "total_insurance_usd"})

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _make_minimal_extraction_app() -> FastAPI:
    """Build a FastAPI app with ONLY the extraction routers.

    Does NOT use app.main — main.py imports analytics routes and all models,
    which would pollute sys.modules and invalidate isolation assertions.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE extracted_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_filename TEXT NOT NULL,
                invoice_number TEXT,
                invoice_date TEXT,
                shipper_name TEXT,
                consignee_name TEXT,
                origin_country TEXT,
                destination_country TEXT,
                shipment_mode TEXT,
                carrier_vendor TEXT,
                total_weight_kg REAL,
                total_freight_cost_usd REAL,
                total_insurance_usd REAL,
                payment_terms TEXT,
                delivery_date TEXT,
                extraction_confidence REAL,
                extracted_at TEXT DEFAULT (datetime('now')),
                confirmed_by_user INTEGER DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE extracted_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                description TEXT,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                confidence REAL
            )
        """))

    Factory = sessionmaker(engine, autocommit=False, autoflush=False)

    app = FastAPI()
    app.include_router(documents.router, prefix="/api")  # POST /api/documents/extract etc.
    app.include_router(extraction.router, prefix="/api")  # DELETE /api/extract/{id}

    def override_get_db():
        db = Factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


def _make_verified_result() -> dict:
    """Return a minimal valid verifier output dict.

    Numeric fields are set to None (columns are nullable) to avoid type
    coercion issues. Text fields use a placeholder string.
    """
    return {
        "fields": {
            name: ExtractedField(
                value=None if name in _NUMERIC_FIELDS else "TEST",
                confidence="HIGH",
            )
            for name in _HEADER_FIELDS
        },
        "line_items": [],
        "low_confidence_fields": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# AC1: Minimal extraction-only app — POST /api/documents/extract works
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionStandaloneApp:
    """POST /api/documents/extract works on a minimal app that has never loaded analytics."""

    def _post_extract(self, client: TestClient):
        """Submit a fake PNG to POST /api/documents/extract with mocked pipeline."""
        mock_executor = MagicMock()
        mock_executor.return_value.extract = AsyncMock(return_value={"raw": "data"})
        mock_verifier = MagicMock()
        vr = _make_verified_result()
        mock_verifier.return_value.score_confidence.return_value = (
            vr["fields"], vr["line_items"], vr["low_confidence_fields"]
        )

        with (
            patch(
                "app.api.routes.documents.ExtractionPlanner.prepare",
                return_value=(_FAKE_PNG, "image/png"),
            ),
            patch("app.api.routes.documents.ExtractionExecutor", mock_executor),
            patch("app.api.routes.documents.ExtractionVerifier", mock_verifier),
            patch("app.api.routes.documents.ModelClient"),
        ):
            return client.post(
                "/api/documents/extract",
                files={"file": ("test.png", _FAKE_PNG, "image/png")},
            )

    def test_post_extract_on_minimal_app_returns_200(self):
        """AC1: Extraction route works on a minimal app with no analytics imports."""
        app = _make_minimal_extraction_app()
        client = TestClient(app)
        response = self._post_extract(client)
        assert response.status_code == 200

    def test_post_extract_response_shape(self):
        """AC1: Response has the correct ExtractionResponse shape."""
        app = _make_minimal_extraction_app()
        client = TestClient(app)
        response = self._post_extract(client)

        body = response.json()
        assert "extraction_id" in body
        assert "filename" in body
        assert "fields" in body
        assert "line_items" in body
        assert body["error"] is None

    def test_post_extract_inserts_db_row(self):
        """AC1: extraction_id is a positive integer — confirms DB row was inserted."""
        app = _make_minimal_extraction_app()
        client = TestClient(app)
        response = self._post_extract(client)

        body = response.json()
        assert body["extraction_id"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# AC2: Static AST analysis — no analytics imports in extraction modules
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionModuleIsolation:
    """All extraction module files must have zero analytics-related imports (AC2).

    Static AST analysis is the most reliable isolation test — it cannot produce
    false positives from sys.modules contamination by other tests.
    """

    @pytest.mark.parametrize("filepath", _EXTRACTION_MODULE_PATHS, ids=lambda p: f"{p.parent.name}/{p.name}")
    def test_no_analytics_imports(self, filepath: pathlib.Path):
        """AC2: Each extraction module file must not import any analytics module."""
        assert filepath.exists(), f"Expected file not found: {filepath}"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(marker in module for marker in _ANALYTICS_MARKERS):
                    violations.append(
                        f"line {node.lineno}: from {module} import ..."
                    )
                for alias in node.names:
                    if any(marker in alias.name for marker in _ANALYTICS_MARKERS):
                        violations.append(
                            f"line {node.lineno}: from {module} import {alias.name} (alias)"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(marker in alias.name for marker in _ANALYTICS_MARKERS):
                        violations.append(
                            f"line {node.lineno}: import {alias.name}"
                        )

        assert not violations, (
            f"{filepath.name} contains analytics import(s):\n"
            + "\n".join(violations)
        )
