"""
Tests for Story 1.1 — Scaffold Backend Project with uv, FastAPI, and Docker

Verifies:
- AC1: GET /docs returns 200 (Swagger UI)
- AC1: GET /api/health returns {"status": "ok"}
- AC1: HTTPException handler returns ErrorResponse shape (not {"detail": ...})
- AC2: config.py loads openrouter_api_key via Pydantic BaseSettings
- AC3: config.py exposes bypass_cache flag
"""
import os
from fastapi.testclient import TestClient

# Provide required env vars before importing app modules
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")


def get_client():
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        client = get_client()
        response = client.get("/api/health")
        assert response.status_code == 200
        # Story 1.4 expanded the response to include database/model fields
        assert response.json()["status"] in ("ok", "degraded")

    def test_swagger_ui_accessible(self):
        client = get_client()
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestHttpExceptionOverride:
    def test_404_returns_error_response_shape(self):
        client = get_client()
        response = client.get("/nonexistent-route-xyz")
        assert response.status_code == 404
        body = response.json()
        # Must NOT be FastAPI default {"detail": "Not Found"}
        assert "detail" not in body
        # Must match ErrorResponse schema
        assert "error" in body
        assert "message" in body
        assert "retry_after" in body


class TestCorsHeaders:
    def test_cors_wildcard_on_health(self):
        client = get_client()
        response = client.options(
            "/api/health",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "GET"},
        )
        # CORS middleware should accept all origins
        assert response.headers.get("access-control-allow-origin") in ("*", "http://example.com")


class TestSettings:
    def test_openrouter_api_key_loaded(self):
        from app.core.config import settings
        assert settings.openrouter_api_key == "test_key_for_tests"

    def test_bypass_cache_default_false(self):
        from app.core.config import settings
        assert settings.bypass_cache is False

    def test_bypass_cache_true_when_env_set(self, monkeypatch):
        monkeypatch.setenv("BYPASS_CACHE", "true")
        from app.core.config import Settings
        fresh = Settings()
        assert fresh.bypass_cache is True

    def test_database_url_has_default(self):
        from app.core.config import settings
        assert "freightmind.db" in settings.database_url

    def test_cache_dir_has_default(self):
        from app.core.config import settings
        assert settings.cache_dir == "./cache"


class TestErrorResponseSchema:
    def test_error_response_all_fields_optional_except_none(self):
        from app.schemas.common import ErrorResponse
        er = ErrorResponse()
        assert er.error is None
        assert er.message is None
        assert er.retry_after is None

    def test_error_response_accepts_values(self):
        from app.schemas.common import ErrorResponse
        er = ErrorResponse(error="http_error", message="Not Found", retry_after=None)
        assert er.error == "http_error"
        assert er.message == "Not Found"
