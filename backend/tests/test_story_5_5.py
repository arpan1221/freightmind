"""
Tests for Story 5.5 — automatic fallback model after primary failure (FR33).
"""

import json
import logging
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIStatusError

from app.core.exceptions import ModelUnavailableError, RateLimitError
from app.services.model_client import ModelClient

PRIMARY_TEXT = "meta-llama/llama-3.3-70b-instruct"
FALLBACK_TEXT = "deepseek/deepseek-r1-0528:free"
PRIMARY_VISION = "qwen/qwen2.5-vl-72b-instruct"
FALLBACK_VISION = "nvidia/nemotron-nano-2-vl:free"


def _make_mock_completion(content: str):
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


def _api_status_502() -> APIStatusError:
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(502, request=req)
    return APIStatusError("bad gateway", response=response, body=None)


def _patch_settings(tmp_path, **overrides):
    """Patch ``model_client.settings`` with Story 5.5–relevant fields."""
    mock_s = MagicMock()
    mock_s.bypass_cache = True
    mock_s.cache_dir = str(tmp_path)
    mock_s.openrouter_api_key = "test"
    mock_s.analytics_model = PRIMARY_TEXT
    mock_s.analytics_model_fallback = FALLBACK_TEXT
    mock_s.vision_model = PRIMARY_VISION
    mock_s.vision_model_fallback = FALLBACK_VISION
    for k, v in overrides.items():
        setattr(mock_s, k, v)
    return patch("app.services.model_client.settings", mock_s)


@pytest.mark.asyncio
async def test_single_shot_primary_fails_fallback_succeeds(tmp_path):
    """Primary 502 → same request on fallback model id; success logs fallback True."""
    calls: list[str] = []

    async def create(**kwargs):
        m = kwargs["model"]
        calls.append(m)
        if m == PRIMARY_TEXT:
            raise _api_status_502()
        if m == FALLBACK_TEXT:
            return _make_mock_completion("fallback-ok")
        raise AssertionError(f"unexpected model {m}")

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            out = await mc.call(PRIMARY_TEXT, [{"role": "user", "content": "hi"}], 0.0)

    assert out == "fallback-ok"
    assert calls == [PRIMARY_TEXT, FALLBACK_TEXT]


@pytest.mark.asyncio
async def test_validation_primary_exhausts_fallback_succeeds(tmp_path):
    """Four bad primary responses, then valid JSON from fallback on first try."""
    primary_left = 4

    async def create(**kwargs):
        nonlocal primary_left
        m = kwargs["model"]
        if m == PRIMARY_TEXT:
            primary_left -= 1
            return _make_mock_completion("not-json")
        if m == FALLBACK_TEXT:
            return _make_mock_completion(json.dumps({"ok": True}))
        raise AssertionError(f"unexpected model {m}")

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            with patch(
                "app.services.model_client.asyncio.sleep", new_callable=AsyncMock
            ):
                out = await mc.call(
                    PRIMARY_TEXT,
                    [{"role": "user", "content": "q"}],
                    0.0,
                    validate=lambda s: json.loads(s),
                )

    assert json.loads(out) == {"ok": True}


@pytest.mark.asyncio
async def test_both_primary_and_fallback_fail_model_unavailable(tmp_path):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    err = APIStatusError("bad", response=httpx.Response(503, request=req), body=None)

    async def create(**kwargs):
        raise err

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            with pytest.raises(ModelUnavailableError) as ei:
                await mc.call(PRIMARY_TEXT, [{"role": "user", "content": "hi"}], 0.0)
            assert "temporarily unavailable" in ei.value.message.lower()


@pytest.mark.asyncio
async def test_429_on_primary_triggers_fallback(tmp_path):
    """Rate limit on primary now falls through to fallback (changed from Story 5.3 original)."""
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    rate_limit_resp = httpx.Response(429, request=req, headers={"retry-after": "60"})
    rate_limit_err = APIStatusError("rate limited", response=rate_limit_resp, body=None)

    calls: list[str] = []

    async def create(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == PRIMARY_TEXT:
            raise rate_limit_err
        return _make_mock_completion("fallback-ok")

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            out = await mc.call(PRIMARY_TEXT, [{"role": "user", "content": "hi"}], 0.0)

    assert out == "fallback-ok"
    assert calls == [PRIMARY_TEXT, FALLBACK_TEXT]


@pytest.mark.asyncio
async def test_429_on_both_primary_and_fallback_raises_unavailable(tmp_path):
    """Rate limit on both primary and fallback → ModelUnavailableError."""
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    rate_limit_resp = httpx.Response(429, request=req, headers={"retry-after": "60"})
    rate_limit_err = APIStatusError("rate limited", response=rate_limit_resp, body=None)

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=rate_limit_err)

            mc = ModelClient(cache_dir=str(tmp_path))
            with pytest.raises(ModelUnavailableError):
                await mc.call(PRIMARY_TEXT, [{"role": "user", "content": "hi"}], 0.0)


@pytest.mark.asyncio
async def test_unknown_primary_no_fallback(tmp_path):
    """Model id not equal to configured primaries → no second attempt."""

    async def create(**kwargs):
        raise _api_status_502()

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            with pytest.raises(ModelUnavailableError):
                await mc.call(
                    "custom/unknown-model", [{"role": "user", "content": "x"}], 0.0
                )

    assert mock_api.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_fallback_success_logs_fallback_true(caplog, tmp_path):
    caplog.set_level(logging.INFO)

    async def create(**kwargs):
        if kwargs["model"] == PRIMARY_TEXT:
            raise _api_status_502()
        return _make_mock_completion("ok")

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            await mc.call(PRIMARY_TEXT, [{"role": "user", "content": "hi"}], 0.0)

    assert any(getattr(r, "fallback", None) is True for r in caplog.records)


@pytest.mark.asyncio
async def test_vision_modality_uses_vision_fallback(tmp_path):
    calls: list[str] = []

    async def create(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == PRIMARY_VISION:
            raise _api_status_502()
        return _make_mock_completion("{}")

    with _patch_settings(tmp_path):
        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=create)

            mc = ModelClient(cache_dir=str(tmp_path))
            await mc.call(
                PRIMARY_VISION,
                [{"role": "user", "content": "hi"}],
                0.0,
                validate=lambda s: json.loads(s),
            )

    assert FALLBACK_VISION in calls
