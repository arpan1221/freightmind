import logging

import httpx
import openai

from app.core.config import settings
from app.services.cache import get_cached_response, make_cache_key, write_cached_response

logger = logging.getLogger(__name__)


class ModelClient:
    """Sole gateway for all LLM API calls via OpenRouter.

    Responsibilities:
    - SHA-256 file-based response cache (read before call, write after call)
    - Configurable cache bypass via BYPASS_CACHE env var (FR44)
    - Structured logging of every call with cache_hit, model_name, retry_count (FR37)
    - 5-second OpenRouter timeout (NFR11)

    Retry logic and model fallback are Epic 5 scope — NOT implemented here.
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        self._cache_dir = cache_dir or settings.cache_dir
        self._client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.AsyncClient(timeout=httpx.Timeout(5.0)),
        )

    async def call(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.0,
    ) -> str:
        """Call the LLM, returning the text content of the first choice.

        Checks the file cache before making a live API call (unless bypass_cache is set).
        Writes the live response to cache after a successful API call.
        """
        cache_key = make_cache_key(model, messages, temperature)

        if not settings.bypass_cache:
            cached = get_cached_response(cache_key, self._cache_dir)
            if cached is not None:
                content = cached.get("content")  # P5: guard against missing key
                if content is not None:
                    logger.info(
                        "ModelClient cache hit",
                        extra={"cache_hit": True, "model_name": model, "retry_count": 0},
                    )
                    return content
                # corrupt/schema-changed cache entry — fall through to live API

        completion = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        # P2: guard against empty choices list or None content
        if not completion.choices:
            raise ValueError(f"OpenRouter returned empty choices list for model '{model}'")
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError(f"OpenRouter returned None content for model '{model}'")

        if not settings.bypass_cache:  # P1: bypass skips write too
            try:
                write_cached_response(cache_key, {"content": content}, self._cache_dir)
            except OSError as e:
                # P4: cache write failure must not discard the live response
                logger.warning("Failed to write cache for key %s: %s", cache_key[:8], e)

        logger.info(
            "ModelClient API call",
            extra={"cache_hit": False, "model_name": model, "retry_count": 0},
        )
        return content
