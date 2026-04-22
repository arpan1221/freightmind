import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, NoReturn

import httpx
import openai
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.core.config import settings
from app.core.exceptions import ModelUnavailableError, RateLimitError
from app.core.retry_after import retry_after_seconds_from_response
from app.core.prompts import load_prompt
from app.services.cache import (
    get_cached_response,
    make_cache_key,
    write_cached_response,
)

logger = logging.getLogger(__name__)

# Sleep before attempts 2–4 after a validation (or transport) failure on the prior attempt.
_RETRY_BACKOFF_SEC = (1, 2, 4)
# Initial attempt + 3 retries = 4 tries total (Epic 5.2).
_MAX_VALIDATION_ATTEMPTS = 4


class ModelClient:
    """Sole gateway for all LLM API calls via OpenRouter.

    Responsibilities:
    - SHA-256 file-based response cache (read before call, write after call)
    - Configurable cache bypass via BYPASS_CACHE env var (FR44)
    - Structured logging of every call with cache_hit, model_name, retry_count (FR37)
    - Optional validation retries with corrective prompt (FR30) when ``validate`` is passed
    - 5-second OpenRouter timeout (NFR11)

    HTTP **429** raises :class:`~app.core.exceptions.RateLimitError` (Story 5.3).
    Connection/timeouts and other transport failures raise
    :class:`~app.core.exceptions.ModelUnavailableError`.

    After the primary model exhausts the Story 5.2 validation loop or fails a single-shot
    API call, a **fallback** model id from settings may be used (Story 5.5). Rate limits
    never trigger fallback.
    """

    _OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        cache_dir: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._cache_dir = cache_dir or settings.cache_dir
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(timeout=httpx.Timeout(timeout)),
        )

    @classmethod
    def for_analytics(cls, timeout: float | None = None) -> "ModelClient":
        """Return a ModelClient wired to the configured analytics provider."""
        resolved_timeout = timeout if timeout is not None else settings.analytics_timeout
        if settings.analytics_provider == "ollama":
            return cls(base_url=settings.ollama_base_url, api_key="ollama", timeout=resolved_timeout)
        return cls(
            base_url=cls._OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key or "",  # validator ensures non-None at startup
            timeout=resolved_timeout,
        )

    @classmethod
    def for_vision(cls, timeout: float = 5.0) -> "ModelClient":
        """Return a ModelClient wired to the configured vision provider."""
        if settings.vision_provider == "ollama":
            return cls(base_url=settings.ollama_base_url, api_key="ollama", timeout=timeout)
        return cls(
            base_url=cls._OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key or "",  # validator ensures non-None at startup
            timeout=timeout,
        )

    async def call(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
        *,
        validate: Callable[[str], None] | None = None,
    ) -> str:
        """Call the LLM, returning the text content of the first choice.

        Without ``validate``: one cache lookup and at most one API call (existing behaviour).

        With ``validate``: up to four attempts with sleeps 1s, 2s, 4s after failures.
        Failures include: optional validation raising, empty choices, or None content.
        Retries append :file:`model_retry_corrective.txt` as a user message.

        If a cache hit returns text that fails ``validate``, that entry is not retried in a
        loop against the same cached bytes — subsequent attempts bypass the cache read and
        call the API (bad cache is overwritten only after a successful validation).

        Successful responses are written under ``make_cache_key(model, messages, temperature)``
        where ``messages`` is the **original** request messages, so callers observe a stable
        cache key regardless of internal retries (per model id, including fallback).
        """
        fb = self._fallback_for(model)
        try:
            if validate is None:
                return await self._call_single_shot(
                    model, messages, temperature, is_fallback=False
                )
            return await self._call_with_validation(
                model, messages, temperature, validate, is_fallback=False
            )
        except Exception as primary_exc:
            if fb is None:
                raise primary_exc
            try:
                if validate is None:
                    return await self._call_single_shot(
                        fb, messages, temperature, is_fallback=True
                    )
                return await self._call_with_validation(
                    fb, messages, temperature, validate, is_fallback=True
                )
            except Exception:
                raise ModelUnavailableError(
                    "The language model is temporarily unavailable. Please try again."
                ) from primary_exc

    async def stream_call(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream assistant text deltas from the chat completion API.

        Does not read or write the response cache (streaming responses are not cached).

        On primary model failure (including rate limits), retries once with the configured
        fallback model (same as :meth:`call`).

        Yields:
            Incremental text fragments from the model's delta content.
        """
        fb = self._fallback_for(model)
        try:
            async for chunk in self._stream_completion(
                model, messages, temperature, is_fallback=False
            ):
                yield chunk
        except Exception as primary_exc:
            if fb is None:
                raise primary_exc
            try:
                async for chunk in self._stream_completion(
                    fb, messages, temperature, is_fallback=True
                ):
                    yield chunk
            except Exception:
                raise ModelUnavailableError(
                    "The language model is temporarily unavailable. Please try again."
                ) from primary_exc
        return

    async def _stream_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        *,
        is_fallback: bool,
    ) -> AsyncIterator[str]:
        """Single streaming completion; logs one API line (not per token)."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        kwargs.setdefault("max_tokens", settings.llm_max_tokens)
        logged = False
        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            self._map_and_raise_sdk_error(e)

        try:
            async for chunk in stream:
                if not logged:
                    logger.info(
                        "ModelClient streaming API call",
                        extra={
                            "cache_hit": False,
                            "model_name": model,
                            "retry_count": 0,
                            "fallback": is_fallback,
                        },
                    )
                    logged = True
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as e:
            self._map_and_raise_sdk_error(e)
        return

    @staticmethod
    def _fallback_for(model: str) -> str | None:
        """Return configured fallback OpenRouter id when ``model`` is a known primary."""
        if model == settings.analytics_model:
            return settings.analytics_model_fallback
        if model == settings.vision_model:
            return settings.vision_model_fallback
        return None

    async def _call_single_shot(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        *,
        is_fallback: bool,
    ) -> str:
        """Single cache read, single API call, no validation retries."""
        cache_key = make_cache_key(model, messages, temperature)

        if not settings.bypass_cache:
            cached = get_cached_response(cache_key, self._cache_dir)
            if cached is not None:
                content = cached.get("content")
                if content is not None:
                    logger.info(
                        "ModelClient cache hit",
                        extra={
                            "cache_hit": True,
                            "model_name": model,
                            "retry_count": 0,
                            "fallback": is_fallback,
                        },
                    )
                    return content

        completion = await self._completion_create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        content = self._extract_message_content(completion, model)

        if not settings.bypass_cache:
            try:
                write_cached_response(cache_key, {"content": content}, self._cache_dir)
            except OSError as e:
                logger.warning("Failed to write cache for key %s: %s", cache_key[:8], e)

        logger.info(
            "ModelClient API call",
            extra={
                "cache_hit": False,
                "model_name": model,
                "retry_count": 0,
                "fallback": is_fallback,
            },
        )
        return content

    async def _call_with_validation(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        validate: Callable[[str], None],
        *,
        is_fallback: bool,
    ) -> str:
        """Retry loop for FR30; corrective text from prompt registry."""
        corrective_text = load_prompt("model_retry_corrective")
        corrective_msg: dict = {"role": "user", "content": corrective_text}
        base_cache_key = make_cache_key(model, messages, temperature)

        for attempt in range(_MAX_VALIDATION_ATTEMPTS):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BACKOFF_SEC[attempt - 1])

            send_messages = messages + ([corrective_msg] if attempt > 0 else [])
            content: str | None = None
            from_cache = False

            if attempt == 0 and not settings.bypass_cache:
                cached = get_cached_response(base_cache_key, self._cache_dir)
                if cached is not None:
                    raw = cached.get("content")
                    if raw is not None:
                        content = raw
                        from_cache = True
                        logger.info(
                            "ModelClient cache hit",
                            extra={
                                "cache_hit": True,
                                "model_name": model,
                                "retry_count": attempt,
                                "fallback": is_fallback,
                            },
                        )

            if content is None:
                completion = await self._completion_create(
                    model=model,
                    messages=send_messages,
                    temperature=temperature,
                )
                try:
                    content = self._extract_message_content(completion, model)
                except ValueError as err:
                    self._log_validation_failure(
                        model, attempt, err, cache_hit=False, is_fallback=is_fallback
                    )
                    if attempt == _MAX_VALIDATION_ATTEMPTS - 1:
                        raise
                    continue

                logger.info(
                    "ModelClient API call",
                    extra={
                        "cache_hit": False,
                        "model_name": model,
                        "retry_count": attempt,
                        "fallback": is_fallback,
                    },
                )

            try:
                validate(content)
            except Exception as err:
                self._log_validation_failure(
                    model, attempt, err, cache_hit=from_cache, is_fallback=is_fallback
                )
                if attempt == _MAX_VALIDATION_ATTEMPTS - 1:
                    raise
                continue

            if not settings.bypass_cache and not from_cache:
                try:
                    write_cached_response(
                        base_cache_key, {"content": content}, self._cache_dir
                    )
                except OSError as e:
                    logger.warning(
                        "Failed to write cache for key %s: %s", base_cache_key[:8], e
                    )
            return content

    async def _completion_create(self, **kwargs: Any) -> object:
        """Invoke chat completions; map SDK/transport errors to Epic 5 exceptions."""
        kwargs.setdefault("max_tokens", settings.llm_max_tokens)
        try:
            return await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            self._map_and_raise_sdk_error(e)

    def _map_and_raise_sdk_error(self, e: Exception) -> NoReturn:
        """Normalize OpenRouter/OpenAI SDK and httpx failures."""
        if isinstance(e, APIStatusError):
            if e.status_code == 429:
                ra = retry_after_seconds_from_response(e.response)
                raise RateLimitError(ra) from e
            if e.status_code == 402:
                raise ModelUnavailableError(
                    "The model provider rejected this request (insufficient credits or "
                    "max output too large). Lower LLM_MAX_TOKENS or add credits, then retry."
                ) from e
            raise ModelUnavailableError(
                "The model service returned an error. Please try again later."
            ) from e
        if isinstance(e, (APIConnectionError, APITimeoutError)):
            raise ModelUnavailableError(
                "The language model is temporarily unavailable. Please try again."
            ) from e
        if isinstance(e, httpx.TimeoutException):
            raise ModelUnavailableError(
                "The request to the language model timed out. Please try again."
            ) from e
        if isinstance(e, httpx.RequestError):
            raise ModelUnavailableError(
                "Could not reach the language model service. Please try again."
            ) from e
        raise e

    def _log_validation_failure(
        self,
        model: str,
        attempt: int,
        err: Exception,
        *,
        cache_hit: bool,
        is_fallback: bool,
    ) -> None:
        """Log failed attempt; max retry_count before raise is 3."""
        log_fn = (
            logger.error if attempt == _MAX_VALIDATION_ATTEMPTS - 1 else logger.warning
        )
        log_fn(
            "ModelClient validation or response failed (attempt %s/%s): %s",
            attempt + 1,
            _MAX_VALIDATION_ATTEMPTS,
            err,
            extra={
                "cache_hit": cache_hit,
                "model_name": model,
                "retry_count": attempt,
                "fallback": is_fallback,
            },
        )

    @staticmethod
    def _extract_message_content(completion: object, model: str) -> str:
        """Return assistant text or raise ValueError for unusable completions."""
        choices = getattr(completion, "choices", None)
        if not choices:
            raise ValueError(
                f"OpenRouter returned empty choices list for model '{model}'"
            )
        msg = choices[0].message
        content = getattr(msg, "content", None)
        if content is None:
            raise ValueError(f"OpenRouter returned None content for model '{model}'")
        return content
