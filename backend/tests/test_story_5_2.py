"""
Tests for Story 5.2 — ModelClient retry with corrective instruction (FR30).

Mocks OpenRouter; patches asyncio.sleep for fast runs.
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache import make_cache_key, write_cached_response
from app.services.model_client import ModelClient


def _make_mock_completion(content: str):
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


@pytest.mark.asyncio
async def test_validate_succeeds_second_attempt_no_extra_sleep_before_first(tmp_path):
    """First attempt fails validation; second succeeds after 1s sleep."""
    sleeps: list[float] = []

    async def track_sleep(delay: float) -> None:
        sleeps.append(delay)

    responses = ["not-json", '{"ok": true}']

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
        mock_api = AsyncMock()
        mock_cls.return_value = mock_api

        async def create_side_effect(**kwargs):
            text = responses.pop(0)
            return _make_mock_completion(text)

        mock_api.chat.completions.create = AsyncMock(side_effect=create_side_effect)

        mc = ModelClient(cache_dir=str(tmp_path))
        with patch("app.services.model_client.asyncio.sleep", side_effect=track_sleep):
            out = await mc.call(
                "m",
                [{"role": "user", "content": "q"}],
                0.0,
                validate=lambda s: __import__("json").loads(s),
            )

    assert out == '{"ok": true}'
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_all_four_attempts_fail_backoff_1_2_4_seconds(tmp_path):
    sleeps: list[float] = []

    async def track_sleep(delay: float) -> None:
        sleeps.append(delay)

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
        mock_api = AsyncMock()
        mock_api.chat.completions.create = AsyncMock(
            return_value=_make_mock_completion("bad")
        )
        mock_cls.return_value = mock_api

        mc = ModelClient(cache_dir=str(tmp_path))
        with patch("app.services.model_client.asyncio.sleep", side_effect=track_sleep):
            with pytest.raises(ValueError, match="bad"):
                await mc.call(
                    "m",
                    [{"role": "user", "content": "q"}],
                    0.0,
                    validate=lambda s: (_ for _ in ()).throw(ValueError("bad")),
                )

    assert sleeps == [1.0, 2.0, 4.0]
    assert mock_api.chat.completions.create.call_count == 4


@pytest.mark.asyncio
async def test_retry_count_in_log_extra(caplog, tmp_path):
    import logging

    caplog.set_level(logging.ERROR)

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
        mock_api = AsyncMock()
        mock_api.chat.completions.create = AsyncMock(
            return_value=_make_mock_completion("x")
        )
        mock_cls.return_value = mock_api

        mc = ModelClient(cache_dir=str(tmp_path))
        with patch("app.services.model_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await mc.call(
                    "test-model",
                    [{"role": "user", "content": "q"}],
                    0.0,
                    validate=lambda s: (_ for _ in ()).throw(ValueError("nope")),
                )

    assert any(getattr(r, "retry_count", None) == 3 for r in caplog.records)


@pytest.mark.asyncio
async def test_bad_cache_bypassed_then_live_succeeds(tmp_path):
    """Cached string fails validate; API returns valid JSON on next attempt."""
    key = make_cache_key("m", [{"role": "user", "content": "q"}], 0.0)
    write_cached_response(key, {"content": "not-json"}, str(tmp_path))

    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
        mock_api = AsyncMock()
        mock_api.chat.completions.create = AsyncMock(
            return_value=_make_mock_completion('{"a": 1}')
        )
        mock_cls.return_value = mock_api

        mc = ModelClient(cache_dir=str(tmp_path))
        with patch("app.services.model_client.asyncio.sleep", new_callable=AsyncMock):
            out = await mc.call(
                "m",
                [{"role": "user", "content": "q"}],
                0.0,
                validate=lambda s: __import__("json").loads(s),
            )

    assert out == '{"a": 1}'
    mock_api.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_single_shot_without_validate_unchanged(tmp_path):
    with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
        mock_api = AsyncMock()
        mock_api.chat.completions.create = AsyncMock(
            return_value=_make_mock_completion("plain")
        )
        mock_cls.return_value = mock_api

        mc = ModelClient(cache_dir=str(tmp_path))
        with patch("app.services.model_client.asyncio.sleep") as mock_sleep:
            out = await mc.call("m", [{"role": "user", "content": "q"}], 0.0)

    assert out == "plain"
    mock_sleep.assert_not_called()
    mock_api.chat.completions.create.assert_called_once()
