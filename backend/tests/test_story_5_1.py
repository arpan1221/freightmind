"""
Tests for Story 5.1 — FastAPI global ErrorResponse envelope (FR29).
"""

import json
import os

from fastapi.testclient import TestClient

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")


def get_client() -> TestClient:
    from app.main import app

    return TestClient(app)


class TestErrorResponseEnvelope:
    def test_404_unknown_route_not_fastapi_detail_only(self) -> None:
        client = get_client()
        response = client.get("/nonexistent-route-story-5-1")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "http_error"
        assert "message" in body
        assert body.get("retry_after") is None

    def test_validation_error_on_malformed_json_body(self) -> None:
        client = get_client()
        response = client.post("/api/query", json={})
        assert response.status_code == 422
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "validation_error"
        assert body["message"]
        assert "errors" in (body.get("detail") or {})

    def test_unhandled_exception_returns_internal_error_envelope(self) -> None:
        from app.main import app

        def boom() -> None:
            raise RuntimeError("secret_internal_detail_do_not_expose")

        app.add_api_route("/__story_5_1_boom", boom, methods=["GET"])
        # Starlette TestClient re-raises route exceptions by default even when the
        # global handler returns a 500 JSON body; disable so we assert the envelope.
        client = TestClient(app, raise_server_exceptions=False)
        try:
            response = client.get("/__story_5_1_boom")
            assert response.status_code == 500
            body = response.json()
            assert body["error"] is True
            assert body["error_type"] == "internal_error"
            assert "secret" not in body["message"]
            assert "secret" not in json.dumps(body)
        finally:
            app.router.routes.pop()


class TestLlmParseErrorHelper:
    def test_llm_parse_error_response_shape(self) -> None:
        from app.api.error_responses import llm_parse_error_response

        resp = llm_parse_error_response("Could not parse model output", detail={"hint": "json"})
        assert resp.status_code == 422
        payload = json.loads(resp.body.decode())
        assert payload["error"] is True
        assert payload["error_type"] == "llm_parse_error"
        assert payload["message"] == "Could not parse model output"
        assert payload["detail"] == {"hint": "json"}
