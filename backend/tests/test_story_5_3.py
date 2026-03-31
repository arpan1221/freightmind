"""
Tests for Story 5.3 — Rate limit (429) and model-unavailable structured errors (FR31 / NFR11).
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.core.exceptions import ModelUnavailableError, RateLimitError
from app.core.retry_after import retry_after_seconds_from_response
from app.services.model_client import ModelClient


class TestRetryAfterHeader:
    def test_numeric_seconds(self):
        r = httpx.Response(429, headers={"retry-after": "45"})
        assert retry_after_seconds_from_response(r) == 45

    def test_missing_header_uses_default(self):
        r = httpx.Response(429, headers={})
        assert retry_after_seconds_from_response(r) == 60

    def test_none_response_uses_default(self):
        assert retry_after_seconds_from_response(None) == 60


class TestModelClientErrorMapping:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_with_retry_after(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx.Response(429, request=req, headers={"retry-after": "88"})
        api_err = APIStatusError("rate limited", response=response, body=None)
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=api_err)
            mc = ModelClient()
            with pytest.raises(RateLimitError) as ei:
                await mc.call("model-x", [{"role": "user", "content": "hi"}], 0.0)
            assert ei.value.retry_after == 88

    @pytest.mark.asyncio
    async def test_402_raises_model_unavailable_with_credits_hint(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx.Response(402, request=req)
        api_err = APIStatusError("payment required", response=response, body=None)
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=api_err)
            mc = ModelClient()
            with pytest.raises(ModelUnavailableError) as ei:
                await mc.call("model-x", [{"role": "user", "content": "hi"}], 0.0)
            assert "LLM_MAX_TOKENS" in str(ei.value.message)

    @pytest.mark.asyncio
    async def test_non_429_api_status_raises_model_unavailable(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx.Response(502, request=req)
        api_err = APIStatusError("bad gateway", response=response, body=None)
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=api_err)
            mc = ModelClient()
            with pytest.raises(ModelUnavailableError):
                await mc.call("model-x", [{"role": "user", "content": "hi"}], 0.0)

    @pytest.mark.asyncio
    async def test_api_connection_error_raises_model_unavailable(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        conn_err = APIConnectionError(request=req)
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=conn_err)
            mc = ModelClient()
            with pytest.raises(ModelUnavailableError):
                await mc.call("model-x", [{"role": "user", "content": "hi"}], 0.0)

    @pytest.mark.asyncio
    async def test_api_timeout_error_raises_model_unavailable(self) -> None:
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        timeout_err = APITimeoutError(req)
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=timeout_err)
            mc = ModelClient()
            with pytest.raises(ModelUnavailableError):
                await mc.call("model-x", [{"role": "user", "content": "hi"}], 0.0)


class TestPostQueryLlmErrors:
    def test_rate_limit_from_classify_returns_envelope(self) -> None:
        from app.main import app

        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner:
            mock_planner = MagicMock()
            mock_planner.classify_intent = AsyncMock(side_effect=RateLimitError(33))
            MockPlanner.return_value = mock_planner

            client = TestClient(app)
            response = client.post("/api/query", json={"question": "test"})

        assert response.status_code == 429
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "rate_limit"
        assert body["retry_after"] == 33
        assert "message" in body

    def test_model_unavailable_from_classify_returns_envelope(self) -> None:
        from app.main import app

        with patch("app.api.routes.analytics.AnalyticsPlanner") as MockPlanner:
            mock_planner = MagicMock()
            mock_planner.classify_intent = AsyncMock(
                side_effect=ModelUnavailableError("upstream down")
            )
            MockPlanner.return_value = mock_planner

            client = TestClient(app)
            response = client.post("/api/query", json={"question": "test"})

        assert response.status_code == 503
        body = response.json()
        assert body["error"] is True
        assert body["error_type"] == "model_unavailable"
        assert body["message"] == "upstream down"
