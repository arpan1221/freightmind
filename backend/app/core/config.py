import logging
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment (see ``backend/.env.example``)."""

    # Required when any provider is "openrouter"; optional when all providers are "ollama".
    openrouter_api_key: str | None = None
    bypass_cache: bool = False
    database_url: str = "sqlite:///./freightmind.db"
    cache_dir: str = "./cache"
    # Inference provider per agent: "openrouter" | "ollama"
    analytics_provider: Literal["openrouter", "ollama"] = "ollama"
    vision_provider: Literal["openrouter", "ollama"] = "openrouter"
    # Ollama base URL — defaults to host.docker.internal for Docker deployments.
    # Override with OLLAMA_BASE_URL=http://localhost:11434/v1 when running the backend directly on the host.
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    analytics_model: str = "llama3.1:8b"
    # Fallback when primary text model fails after retries (Story 5.5, TECH_DECISIONS TD-2).
    analytics_model_fallback: str = "llama3.1:8b"
    vision_model: str = "nvidia/nemotron-nano-12b-v2-vl:free"
    # Fallback when primary vision model fails after retries (Story 5.5, TECH_DECISIONS TD-3).
    vision_model_fallback: str = "qwen/qwen2.5-vl-7b-instruct:free"
    # Timeout for analytics (text) LLM calls. Local Ollama models can be slow — 60s default.
    analytics_timeout: float = 60.0
    vision_timeout: float = 300.0
    # Passed to OpenRouter as max_tokens on every chat completion. High defaults (e.g. model
    # max) can trigger 402 on low-credit accounts; keep this within typical output needs.
    llm_max_tokens: int = 2048
    # Comma-separated origins, or "*" for all (local dev). Production: list explicit UI origins.
    cors_origins: str = "*"
    # Maximum upload size for POST /api/documents/extract (bytes).
    max_upload_bytes: int = 10 * 1024 * 1024
    # Live seeding: drip synthetic rows into shipments at this interval (seconds).
    # 0 = disabled (default). Set to e.g. 30 in .env for demo live-data effect.
    live_seeding_interval_seconds: int = 0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def require_openrouter_key_when_needed(self) -> Self:
        """Raise at startup if OpenRouter is selected but no API key is provided."""
        needs_key = (
            self.analytics_provider == "openrouter"
            or self.vision_provider == "openrouter"
        )
        if needs_key and not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required when ANALYTICS_PROVIDER or "
                "VISION_PROVIDER is set to 'openrouter'."
            )
        return self

    @model_validator(mode="after")
    def warn_duplicate_fallback_models(self) -> Self:
        """Avoid redundant second model phase when primary and fallback ids match (deferred 5.5)."""
        if self.analytics_model.strip() == self.analytics_model_fallback.strip():
            logger.warning(
                "ANALYTICS_MODEL and ANALYTICS_MODEL_FALLBACK are identical; "
                "fallback will call the same model twice on failure."
            )
        if self.vision_model.strip() == self.vision_model_fallback.strip():
            logger.warning(
                "VISION_MODEL and VISION_MODEL_FALLBACK are identical; "
                "fallback will call the same model twice on failure."
            )
        return self


def cors_allow_origins_list(settings: Settings) -> list[str]:
    """Parse CORS_ORIGINS: ``*`` or comma-separated list."""
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
