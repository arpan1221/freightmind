"""
Tests for Story 1.4 — Health Check Endpoint

Verifies:
- AC1: DB accessible + model reachable → {"status": "ok", "database": "connected", "model": "reachable"}, HTTP 200
- AC2: DB error (including session-creation failure) → {"status": "degraded", ...}, still HTTP 200 (never 5xx)
- AC3: Model unreachable → {"status": "degraded", ..., "model": "unreachable"}, still HTTP 200
- Response shape always contains all three keys (status, database, model)
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from app.main import app  # noqa: E402


def _make_in_memory_session_factory():
    """Return a SessionLocal-compatible factory backed by in-memory SQLite."""
    from app.core.database import Base
    import app.models.shipment  # noqa: F401
    import app.models.extracted_document  # noqa: F401
    import app.models.extracted_line_item  # noqa: F401
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
    return sessionmaker(engine)


def _make_broken_session_factory():
    """Return a session factory whose execute() raises, simulating DB error."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("simulated DB failure")
    factory = MagicMock(return_value=mock_session)
    return factory


@pytest.fixture
def client():
    """Bare TestClient — SessionLocal patched per-test."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# AC1: DB up + model up → status ok
# ---------------------------------------------------------------------------

class TestHealthAllOk:
    def test_returns_200(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_in_memory_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_full_ok_body(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_in_memory_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        assert resp.json() == {"status": "ok", "database": "connected", "model": "reachable"}

    def test_response_shape_has_all_three_keys(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_in_memory_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        body = resp.json()
        assert "status" in body
        assert "database" in body
        assert "model" in body


# ---------------------------------------------------------------------------
# AC2: DB error → status degraded, still HTTP 200
# ---------------------------------------------------------------------------

class TestHealthDbError:
    def test_db_execute_error_returns_200(self, client):
        """execute() raises — caught inside handler."""
        with patch("app.api.routes.system.SessionLocal", _make_broken_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_db_execute_error_body(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_broken_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] == "error"
        assert body["model"] == "reachable"

    def test_session_creation_failure_returns_200(self, client):
        """SessionLocal() itself raises — the fix for the 5xx regression.
        Previously, using Depends(get_db) would allow this exception to escape
        the route's try/except and return 500. Now SessionLocal() is called
        inside the try block, so any failure is caught correctly.
        """
        factory_that_raises = MagicMock(side_effect=Exception("pool exhausted"))
        with patch("app.api.routes.system.SessionLocal", factory_that_raises):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] == "error"

    def test_db_file_missing_returns_degraded(self, client):
        """Broken SQLite path → OperationalError on execute → 'error'."""
        bad_engine = create_engine(
            "sqlite:////nonexistent/path/to/db.sqlite",
            connect_args={"check_same_thread": False},
        )
        with patch("app.api.routes.system.SessionLocal", sessionmaker(bad_engine)):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="reachable"):
                resp = client.get("/api/health")
        body = resp.json()
        assert resp.status_code == 200
        assert body["status"] == "degraded"
        assert body["database"] == "error"
        assert body["model"] == "reachable"


# ---------------------------------------------------------------------------
# AC3: Model unreachable → status degraded, still HTTP 200
# ---------------------------------------------------------------------------

class TestHealthModelUnreachable:
    def test_model_unreachable_returns_200(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_in_memory_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="unreachable"):
                resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_model_unreachable_body(self, client):
        with patch("app.api.routes.system.SessionLocal", _make_in_memory_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="unreachable"):
                resp = client.get("/api/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database"] == "connected"
        assert body["model"] == "unreachable"

    def test_both_degraded(self, client):
        """Both DB error and model unreachable → degraded."""
        with patch("app.api.routes.system.SessionLocal", _make_broken_session_factory()):
            with patch("app.api.routes.system._check_model", new_callable=AsyncMock, return_value="unreachable"):
                resp = client.get("/api/health")
        body = resp.json()
        assert resp.status_code == 200
        assert body["status"] == "degraded"
        assert body["database"] == "error"
        assert body["model"] == "unreachable"


# ---------------------------------------------------------------------------
# _check_model unit tests — no HTTP needed
# ---------------------------------------------------------------------------

class TestCheckModelUnit:
    @pytest.mark.asyncio
    async def test_check_model_returns_reachable_on_success(self):
        from app.api.routes.system import _check_model

        mock_response = httpx.Response(200)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await _check_model()
        assert result == "reachable"

    @pytest.mark.asyncio
    async def test_check_model_returns_unreachable_on_exception(self):
        from app.api.routes.system import _check_model

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
            result = await _check_model()
        assert result == "unreachable"

    @pytest.mark.asyncio
    async def test_check_model_returns_unreachable_on_timeout(self):
        from app.api.routes.system import _check_model

        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
            result = await _check_model()
        assert result == "unreachable"

    @pytest.mark.asyncio
    async def test_check_model_returns_unreachable_on_4xx(self):
        from app.api.routes.system import _check_model

        mock_response = httpx.Response(401)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await _check_model()
        assert result == "unreachable"
