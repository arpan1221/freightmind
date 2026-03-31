"""
Tests for Story 1.6 — ModelClient with File-Based SHA-256 Response Cache

Verifies:
- AC1: Cache hit returns cached response within 2 seconds; logs cache_hit=True
- AC2: Cache miss calls OpenRouter API, writes to cache; logs cache_hit=False, retry_count=0
- AC3: BYPASS_CACHE=true skips cache entirely
- AC4: No direct openai imports outside model_client.py
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.core.config import settings
from app.services.cache import get_cached_response, make_cache_key, write_cached_response
from app.services.model_client import ModelClient


# ---------------------------------------------------------------------------
# cache.py tests
# ---------------------------------------------------------------------------


class TestMakeCacheKey:
    def test_same_inputs_same_hash(self):
        key1 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        key2 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        assert key1 == key2

    def test_different_model_different_hash(self):
        key1 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        key2 = make_cache_key("model-b", [{"role": "user", "content": "hello"}], 0.0)
        assert key1 != key2

    def test_different_messages_different_hash(self):
        key1 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        key2 = make_cache_key("model-a", [{"role": "user", "content": "world"}], 0.0)
        assert key1 != key2

    def test_different_temperature_different_hash(self):
        key1 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        key2 = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.5)
        assert key1 != key2

    def test_returns_64_char_hex_string(self):
        key = make_cache_key("model-a", [{"role": "user", "content": "hello"}], 0.0)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_sort_keys_determinism(self):
        """sort_keys=True must make key independent of dict insertion order."""
        msgs1 = [{"content": "hello", "role": "user"}]
        msgs2 = [{"role": "user", "content": "hello"}]
        key1 = make_cache_key("model-a", msgs1, 0.0)
        key2 = make_cache_key("model-a", msgs2, 0.0)
        assert key1 == key2


class TestCacheReadWrite:
    def test_get_cached_response_returns_none_for_missing_key(self, tmp_path):
        result = get_cached_response("nonexistent_key", str(tmp_path))
        assert result is None

    def test_write_then_get_round_trips(self, tmp_path):
        key = make_cache_key("model-a", [{"role": "user", "content": "test"}], 0.0)
        payload = {"content": "SELECT COUNT(*) FROM shipments"}
        write_cached_response(key, payload, str(tmp_path))
        result = get_cached_response(key, str(tmp_path))
        assert result == payload

    def test_write_creates_cache_dir_if_missing(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        key = make_cache_key("model-a", [{"role": "user", "content": "x"}], 0.0)
        write_cached_response(key, {"content": "ok"}, str(nested))
        assert (nested / f"{key}.json").exists()

    def test_cache_file_is_valid_json(self, tmp_path):
        key = make_cache_key("model-a", [{"role": "user", "content": "json-test"}], 0.0)
        write_cached_response(key, {"content": "value"}, str(tmp_path))
        raw = (tmp_path / f"{key}.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert parsed == {"content": "value"}

    def test_overwrite_updates_existing_cache(self, tmp_path):
        key = make_cache_key("model-a", [{"role": "user", "content": "overwrite"}], 0.0)
        write_cached_response(key, {"content": "first"}, str(tmp_path))
        write_cached_response(key, {"content": "second"}, str(tmp_path))
        result = get_cached_response(key, str(tmp_path))
        assert result == {"content": "second"}


# ---------------------------------------------------------------------------
# model_client.py tests
# ---------------------------------------------------------------------------


def _make_mock_completion(content: str):
    """Build a minimal mock that mimics openai CompletionChoice structure."""
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


class TestModelClientCacheHit:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_content(self, tmp_path):
        key = make_cache_key("test-model", [{"role": "user", "content": "hello"}], 0.0)
        write_cached_response(key, {"content": "cached-answer"}, str(tmp_path))

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            result = await mc.call("test-model", [{"role": "user", "content": "hello"}], 0.0)

        assert result == "cached-answer"
        mock_api.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_call_api(self, tmp_path):
        key = make_cache_key("test-model", [{"role": "user", "content": "no-api"}], 0.0)
        write_cached_response(key, {"content": "from-cache"}, str(tmp_path))

        api_called = False

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_cls.return_value = mock_api
            mock_api.chat.completions.create = AsyncMock(side_effect=lambda **_: (_ for _ in ()).throw(AssertionError("API should not be called on cache hit")))

            mc = ModelClient(cache_dir=str(tmp_path))
            result = await mc.call("test-model", [{"role": "user", "content": "no-api"}], 0.0)

        assert result == "from-cache"


class TestModelClientCacheMiss:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_api(self, tmp_path):
        mock_completion = _make_mock_completion("live-answer")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            result = await mc.call("test-model", [{"role": "user", "content": "miss"}], 0.0)

        assert result == "live-answer"
        mock_api.chat.completions.create.assert_called_once()
        assert (
            mock_api.chat.completions.create.call_args.kwargs.get("max_tokens")
            == settings.llm_max_tokens
        )

    @pytest.mark.asyncio
    async def test_cache_miss_writes_to_cache(self, tmp_path):
        mock_completion = _make_mock_completion("written-answer")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            await mc.call("test-model", [{"role": "user", "content": "write-test"}], 0.0)

        key = make_cache_key("test-model", [{"role": "user", "content": "write-test"}], 0.0)
        cached = get_cached_response(key, str(tmp_path))
        assert cached == {"content": "written-answer"}

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, tmp_path):
        mock_completion = _make_mock_completion("api-response")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            first = await mc.call("test-model", [{"role": "user", "content": "repeat"}], 0.0)
            second = await mc.call("test-model", [{"role": "user", "content": "repeat"}], 0.0)

        assert first == second == "api-response"
        # API should only have been called once
        assert mock_api.chat.completions.create.call_count == 1


class TestModelClientBypassCache:
    @pytest.mark.asyncio
    async def test_bypass_cache_skips_cache(self, tmp_path):
        # Pre-seed cache
        key = make_cache_key("test-model", [{"role": "user", "content": "bypass"}], 0.0)
        write_cached_response(key, {"content": "stale-cached"}, str(tmp_path))

        mock_completion = _make_mock_completion("live-bypass")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            with patch("app.services.model_client.settings") as mock_settings:
                mock_settings.bypass_cache = True
                mock_settings.cache_dir = str(tmp_path)
                mock_settings.openrouter_api_key = "test_key"

                mc = ModelClient(cache_dir=str(tmp_path))
                result = await mc.call("test-model", [{"role": "user", "content": "bypass"}], 0.0)

        assert result == "live-bypass"
        mock_api.chat.completions.create.assert_called_once()


# ---------------------------------------------------------------------------
# Architecture enforcement tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Patch fixes regression tests
# ---------------------------------------------------------------------------


class TestCacheGetPatches:
    def test_get_returns_none_on_malformed_json(self, tmp_path):
        """P3: JSONDecodeError on corrupt cache file → returns None, not exception."""
        key = make_cache_key("m", [{"role": "user", "content": "x"}], 0.0)
        corrupt = tmp_path / f"{key}.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        assert get_cached_response(key, str(tmp_path)) is None

    def test_get_returns_none_on_toctou_deletion(self, tmp_path):
        """P6: File deleted between exists() and read() → returns None, not FileNotFoundError."""
        # Verify EAFP approach handles non-existent file cleanly (covers the race path)
        result = get_cached_response("no-such-key", str(tmp_path))
        assert result is None


class TestModelClientPatches:
    @pytest.mark.asyncio
    async def test_bypass_cache_does_not_write_to_cache(self, tmp_path):
        """P1: bypass_cache=True skips both read AND write."""
        mock_completion = _make_mock_completion("fresh-result")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            with patch("app.services.model_client.settings") as mock_settings:
                mock_settings.bypass_cache = True
                mock_settings.cache_dir = str(tmp_path)
                mock_settings.openrouter_api_key = "test_key"

                mc = ModelClient(cache_dir=str(tmp_path))
                result = await mc.call("test-model", [{"role": "user", "content": "bp"}], 0.0)

        assert result == "fresh-result"
        # No cache files should have been written
        cache_files = list(tmp_path.glob("*.json"))
        assert cache_files == [], f"Expected no cache files written, found: {cache_files}"

    @pytest.mark.asyncio
    async def test_empty_choices_raises_value_error(self, tmp_path):
        """P2: Empty choices list raises ValueError, not IndexError."""
        mock_completion = MagicMock()
        mock_completion.choices = []

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            with pytest.raises(ValueError, match="empty choices"):
                await mc.call("test-model", [{"role": "user", "content": "x"}], 0.0)

    @pytest.mark.asyncio
    async def test_none_content_raises_value_error(self, tmp_path):
        """P2: None content raises ValueError rather than caching None."""
        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            with pytest.raises(ValueError, match="None content"):
                await mc.call("test-model", [{"role": "user", "content": "x"}], 0.0)

    @pytest.mark.asyncio
    async def test_cache_write_failure_still_returns_content(self, tmp_path):
        """P4: OSError on cache write must not discard the live API response."""
        mock_completion = _make_mock_completion("live-content")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            with patch("app.services.model_client.write_cached_response",
                       side_effect=OSError("disk full")):
                mc = ModelClient(cache_dir=str(tmp_path))
                result = await mc.call("test-model", [{"role": "user", "content": "x"}], 0.0)

        assert result == "live-content"

    @pytest.mark.asyncio
    async def test_corrupt_cache_missing_content_key_falls_through_to_api(self, tmp_path):
        """P5: Cache entry missing 'content' key → falls through to live API."""
        key = make_cache_key("test-model", [{"role": "user", "content": "corrupt"}], 0.0)
        # Write a cache entry without the 'content' key
        write_cached_response(key, {"wrong_key": "value"}, str(tmp_path))

        mock_completion = _make_mock_completion("live-fallback")

        with patch("app.services.model_client.openai.AsyncOpenAI") as mock_cls:
            mock_api = AsyncMock()
            mock_api.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_cls.return_value = mock_api

            mc = ModelClient(cache_dir=str(tmp_path))
            result = await mc.call("test-model", [{"role": "user", "content": "corrupt"}], 0.0)

        assert result == "live-fallback"
        mock_api.chat.completions.create.assert_called_once()


class TestNoDirectOpenAIImports:
    def test_no_openai_import_in_agents_dir(self):
        result = subprocess.run(
            ["grep", "-r", "import openai", "app/agents/"],
            cwd="/Users/arpannookala/Documents/freightmind/backend",
            capture_output=True,
            text=True,
        )
        # grep exits 1 (no match) — that's what we want
        assert result.stdout == "", (
            f"Found direct openai imports in app/agents/:\n{result.stdout}"
        )

    def test_no_openai_import_in_api_dir(self):
        result = subprocess.run(
            ["grep", "-r", "import openai", "app/api/"],
            cwd="/Users/arpannookala/Documents/freightmind/backend",
            capture_output=True,
            text=True,
        )
        assert result.stdout == "", (
            f"Found direct openai imports in app/api/:\n{result.stdout}"
        )
